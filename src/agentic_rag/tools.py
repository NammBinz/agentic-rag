"""Deterministic academic tools with explicit unknowns and snapshot-only results."""
import math
from .catalog import SUPPORTED_COHORTS, course_codes, normalize


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

    def catalog_summary(self, cohort, subset='all', group=None):
        """Count distinct scoped catalog codes, using the source selection rule exactly."""
        if cohort != self.catalog.cohort:
            return AcademicTools(self.catalog.for_cohort(cohort)).catalog_summary(cohort, subset, group)
        if subset not in ('all', 'mandatory', 'choices'):
            raise ValueError('Tập học phần không hợp lệ')
        result = {'tool': 'catalog_summary', 'status': 'insufficient_data', 'courses': [],
                  'count': 0, 'catalog_count': len(self.catalog.courses), 'groups': [],
                  'choice_groups': [], 'citations': [], 'context': self.catalog.context,
                  'subset': subset, 'group': group}
        if self.catalog.context['status'] != 'verified_snapshot':
            return {**result, 'message': self.catalog.context['message']}
        records = [c for c in self.catalog.courses.values() if group is None or c['group'] == group]
        fixed = lambda c: normalize(c.get('selection_rule') or '').strip() == 'bat buoc theo muc khung'
        selected = [c for c in records if subset == 'all' or (fixed(c) if subset == 'mandatory' else not fixed(c))]
        selected.sort(key=lambda c: (c.get('workbook_row') or 0, c['code']))
        by_id = {c['id']: c for c in self.catalog.chunks if c['kind'] == 'course'}
        def summarize(rows, keys):
            grouped = {}
            for c in rows:
                key = tuple(c[k] for k in keys)
                grouped.setdefault(key, []).append(c)
            return [{**dict(zip(keys, key)), 'count': len(values), 'codes': [c['code'] for c in values]}
                    for key, values in grouped.items()]
        result.update(status='catalog_summary', count=len(selected), courses=selected,
                      groups=summarize(selected, ['group']),
                      choice_groups=summarize([c for c in records if not fixed(c)], ['group', 'selection_rule']),
                      # All records used in computing this scoped report remain inspectable.
                      citations=[self.catalog.citation(by_id[self.catalog.course_chunk_id(c)]) for c in records],
                      message='Thống kê theo mã học phần trong toàn bộ danh mục đúng khóa/phiên bản; không theo số đoạn truy xuất.')
        return result

    def conditions(self, code, cohort, depth=0, profile=None):
        """Read recorded conditions; at most two reference edges, never infer eligibility."""
        if not isinstance(depth, int) or isinstance(depth, bool) or not 0 <= depth <= 2:
            raise ValueError('depth phải từ 0 đến 2')
        lookup = self.lookup(code, cohort)
        result = {'tool': 'lookup_conditions', 'status': 'insufficient_data',
                  'course_code': code.strip().upper(), 'nodes': [], 'edges': [],
                  'missing_references': [], 'citations': [], 'max_depth': depth,
                  'scope': 'Chuỗi mã được ghi trong bảng; không suy ra học trước/đạt môn hoặc quyền đăng ký.'}
        if lookup['status'] != 'found' or len(lookup['courses']) != 1:
            return {**result, 'message': lookup['message'],
                    'status': lookup['status'] if lookup['status'] != 'found' else 'needs_input'}
        catalog = self.catalog.for_cohort(cohort)
        root = lookup['courses'][0]['code']
        result['course_code'] = root
        queue, visited = [(root, 0, ())], set()
        chunks = {c.get('course_code'): c for c in catalog.chunks if c['kind'] == 'course'}
        while queue and len(visited) < 25:
            current, level, path = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            course = catalog.courses.get(current)
            if not course:
                result['missing_references'].append(current)
                continue
            components = [c for c in catalog.conditions if c['course'] == current]
            result['nodes'].append({'course_code': current, 'depth': level,
                'prerequisite_raw': course['prerequisite_raw'], 'prerequisite_status': course['prerequisite_status'],
                'components': components, 'workbook_sheet': course.get('workbook_sheet'),
                'workbook_row': course.get('workbook_row')})
            result['citations'].append(catalog.citation(chunks[current]))
            for reference in course_codes(course['prerequisite_raw'] or ''):
                cyclic = reference in (*path, current)
                result['edges'].append({'from': current, 'to': reference, 'cycle': cyclic,
                                       'reference_found': reference in catalog.courses})
                if reference not in catalog.courses:
                    if reference not in result['missing_references']:
                        result['missing_references'].append(reference)
                elif level < depth and not cyclic:
                    queue.append((reference, level + 1, (*path, current)))
        blank = lookup['courses'][0]['prerequisite_status'] == 'SOURCE_BLANK'
        result.update(status='insufficient_data' if blank or result['missing_references'] else 'recorded_conditions',
            message=('Ô tiên quyết trống: chưa đủ căn cứ kết luận không có điều kiện.' if blank else
                     'Thuật lại điều kiện và chuỗi tham chiếu đúng như bảng, không tự thêm ngưỡng điểm.'))
        if result['missing_references']:
            result['message'] += ' Thiếu bản ghi: ' + ', '.join(result['missing_references']) + '.'
        if profile is not None:
            result['evaluation'] = self.prerequisites(root, cohort, profile)
        return result

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
