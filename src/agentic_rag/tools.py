"""Deterministic academic tools with explicit unknowns and snapshot-only results."""
import math
from .catalog import SUPPORTED_COHORTS


def validate_profile(profile):
    if profile is None:
        return None
    if not isinstance(profile, dict) or set(profile) - {"completed", "grades", "credits", "average"}:
        raise ValueError("Hồ sơ chỉ nhận completed, grades, credits, average")
    completed = profile.get("completed")
    if completed is not None and (not isinstance(completed, list) or len(completed) > 200 or
                                 any(not isinstance(c, str) or len(c) > 20 for c in completed)):
        raise ValueError("completed phải là danh sách mã môn (hoặc null nếu chưa biết)")
    grades = profile.get("grades", {})
    if not isinstance(grades, dict) or len(grades) > 200:
        raise ValueError("grades phải là object mã môn: điểm")
    def numeric(value, lower, upper):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and lower <= value <= upper
    if any(not isinstance(code, str) or not numeric(grade, 0, 10) for code, grade in grades.items()):
        raise ValueError("Điểm phải là số hữu hạn từ 0 đến 10")
    for field, maximum in (("credits", 1000), ("average", 10)):
        if profile.get(field) is not None and not numeric(profile[field], 0, maximum):
            raise ValueError(f"{field} ngoài miền hợp lệ")
    return {"completed": None if completed is None else list(dict.fromkeys(c.strip().upper() for c in completed)),
            "grades": {c.strip().upper(): v for c, v in grades.items()},
            "credits": profile.get("credits"), "average": profile.get("average")}


class AcademicTools:
    def __init__(self, catalog):
        self.catalog = catalog

    def lookup(self, query, cohort):
        if cohort != self.catalog.cohort:
            return AcademicTools(self.catalog.for_cohort(cohort)).lookup(query, cohort)
        if cohort not in SUPPORTED_COHORTS:
            return {"tool": "lookup_course", "status": "needs_input" if not cohort else "out_of_scope",
                    "message": "Cần chọn khóa K35–K39; không suy rộng dữ liệu cho khóa khác.", "courses": [], "citations": []}
        if self.catalog.context['status'] != 'verified_snapshot':
            return {"tool": "lookup_course", "status": "insufficient_data", "courses": [], "citations": [],
                    "context": self.catalog.context, "message": self.catalog.context['message']}
        found = self.catalog.select_courses(query)
        by_id = {c["id"]: c for c in self.catalog.chunks}
        return {"tool": "lookup_course", "status": "found" if found else "not_found",
                "courses": found, "message": f"Tìm được {len(found)} học phần trong snapshot.",
                "context": self.catalog.context,
                "citations": [self.catalog.citation(by_id[self.catalog.course_chunk_id(c)]) for c in found]}

    def _leaf(self, condition, profile):
        kind, reference = condition["kind"], condition["reference"]
        base = {"id": condition["id"], "kind": kind, "reference": reference,
                "threshold": condition.get("threshold"), "quote": condition["quote"],
                "status": "unknown", "actual": None}
        if condition.get("status") not in ("VERIFIED_TRANSCRIPTION", "SYNTHETIC_VERIFIED"):
            return {**base, "reason": "Điều kiện chưa được xác minh."}
        if kind == "COURSE_CODE":
            base["present_in_completed"] = reference in (profile.get("completed") or [])
            return {**base, "reason": "Nguồn chỉ ghi mã; chưa xác minh nghĩa học trước/đạt môn hoặc ngưỡng. Không tự diễn giải."}
        if kind == "COURSE_COMPLETED":
            if profile.get("completed") is None:
                return {**base, "reason": "Chưa cung cấp danh sách môn đã đạt."}
            actual = reference in profile["completed"]
            return {**base, "actual": actual, "status": "satisfied" if actual else "not_met",
                    "reason": "Đối chiếu danh sách môn đã đạt do người dùng khai."}
        fields = {"COURSE_SCORE_MIN": (profile.get("grades", {}).get(reference), "điểm " + str(reference)),
                  "ACCUMULATED_CREDITS_MIN": (profile.get("credits"), "tín chỉ tích lũy"),
                  "ACCUMULATED_AVERAGE_MIN": (profile.get("average"), "điểm trung bình tích lũy")}
        if kind not in fields or condition.get("operator") != ">=":
            return {**base, "reason": "Loại/toán tử điều kiện chưa được hỗ trợ; cần xác minh."}
        actual, label = fields[kind]
        if actual is None:
            return {**base, "reason": "Chưa cung cấp " + label + "."}
        threshold = condition.get("threshold")
        if not isinstance(threshold, (int, float)):
            return {**base, "reason": "Nguồn thiếu ngưỡng số."}
        return {**base, "actual": actual, "status": "satisfied" if actual >= threshold else "not_met",
                "reason": f"{label}: {actual} >= {threshold}."}

    def _tree(self, node, profile, by_id):
        if "condition" in node:
            condition = by_id.get(node["condition"])
            if not condition:
                return {"status": "unknown", "reason": "Thiếu bản ghi điều kiện", "id": node["condition"]}
            return self._leaf(condition, profile)
        op = node.get("op")
        if op not in ("all", "any") or not isinstance(node.get("children"), list) or not node["children"]:
            return {"status": "unknown", "reason": "Biểu thức AND/OR chưa hợp lệ"}
        children = [self._tree(c, profile, by_id) for c in node["children"]]
        states = [c["status"] for c in children]
        if op == "all":
            state = "not_met" if "not_met" in states else ("satisfied" if all(s == "satisfied" for s in states) else "unknown")
        else:
            state = "satisfied" if "satisfied" in states else ("not_met" if all(s == "not_met" for s in states) else "unknown")
        return {"op": op, "status": state, "children": children}

    def prerequisites(self, code, cohort, profile=None):
        if cohort != self.catalog.cohort:
            return AcademicTools(self.catalog.for_cohort(cohort)).prerequisites(code, cohort, profile)
        profile = validate_profile(profile)
        lookup = self.lookup(code, cohort)
        result = {"tool": "check_prerequisites", "course_code": code.strip().upper(),
                  "status": "insufficient_data", "missing": [], "checks": [], "citations": lookup["citations"],
                  "context": self.catalog.context,
                  "scope": "Chỉ đối chiếu điều kiện trong snapshot đúng khóa/phiên bản; không xác nhận quyền đăng ký thực tế."}
        if lookup["status"] != "found":
            return {**result, "status": lookup["status"], "message": lookup["message"]}
        if len(lookup["courses"]) != 1:
            return {**result, "status": "needs_input", "message": "Cần chọn đúng một mã học phần."}
        course = lookup["courses"][0]
        result["course_code"] = course["code"]
        if course["prerequisite_status"] == "SOURCE_BLANK":
            return {**result, "message": "Ô tiên quyết trống trong nguồn; chưa thể kết luận không có tiên quyết."}
        if profile is None:
            return {**result, "status": "needs_input", "message": "Cần hồ sơ giả lập: môn đã đạt/điểm/tín chỉ tùy điều kiện."}
        conditions = [c for c in self.catalog.conditions if c["course"] == course["code"]]
        if not conditions:
            return {**result, "message": "Chưa có điều kiện được chuẩn hóa để kiểm tra."}
        tree = course.get("rule") or {"op": "all", "children": [{"condition": c["id"]} for c in conditions]}
        evaluation = self._tree(tree, profile, {c["id"]: c for c in conditions})
        leaves = []
        def collect(node):
            if "children" in node:
                for c in node["children"]:
                    collect(c)
            else:
                leaves.append(node)
        collect(evaluation)
        result.update(checks=leaves, expression=evaluation,
                      missing=[{"reference": c.get("reference"), "reason": c["reason"], "status": c["status"]}
                               for c in leaves if c["status"] != "satisfied"])
        state = evaluation["status"]
        status = {"satisfied": "satisfied_in_snapshot", "not_met": "not_met_in_snapshot", "unknown": "insufficient_data"}[state]
        messages = {"satisfied": "Các điều kiện đã xác định trong snapshot đều thỏa với hồ sơ khai báo.",
                    "not_met": "Có điều kiện đã xác định trong snapshot chưa thỏa với hồ sơ khai báo.",
                    "unknown": "Chưa đủ thông tin hoặc chưa xác minh cách hiểu điều kiện; chưa thể kết luận."}
        # Do not present unused OR branches as mandatory missing courses.
        if state == "satisfied":
            result["missing"] = []
        return {**result, "status": status, "message": messages[state]}
