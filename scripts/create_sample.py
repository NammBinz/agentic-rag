"""Build synthetic fixtures; never mix these records with the project catalog."""
import json
from pathlib import Path


def create(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    names = {"PY101": "Python nhập môn", "CS101": "Cơ sở lập trình", "PY201": "Python ứng dụng",
             "PY202": "Dự án Python", "PY203": "Phân tích dữ liệu", "PY204": "Thực hành chưa xác minh"}
    courses = []
    rules = {"PY201": ("all", ["T01", "T02"]), "PY202": ("any", ["T03", "T04"]),
             "PY203": ("all", ["T05", "T06"])}
    for i, (code, name) in enumerate(names.items(), 1):
        course = {"code": code, "name": name, "credits": 3, "group": "Giả lập",
                  "selection_rule": "Chỉ dùng kiểm thử", "prerequisite_raw": None,
                  "prerequisite_status": "SOURCE_BLANK", "page": i, "source_rows": f"TEST-{i}",
                  "source_row_count": 1, "source_id": "TEST", "cohort": "K37", "version": "sample-v1",
                  "verification": "SYNTHETIC_VERIFIED", "current_amendments_verified": True, "limitations": None}
        if code in rules:
            op, ids = rules[code]
            raw = {"PY201": "Đã đạt PY101 VÀ tích lũy ít nhất 12 tín chỉ",
                   "PY202": "Đã đạt PY101 HOẶC CS101 >= 7",
                   "PY203": "PY101 >= 5 VÀ TBTL >= 6"}[code]
            course.update(prerequisite_raw=raw, prerequisite_status="SYNTHETIC_VERIFIED",
                          rule={"op": op, "children": [{"condition": x} for x in ids]})
        courses.append(course)
    conditions = []
    definitions = [("T01", "PY201", "COURSE_COMPLETED", "PY101", None, "Đã đạt PY101"),
                   ("T02", "PY201", "ACCUMULATED_CREDITS_MIN", None, 12, "Tích lũy ít nhất 12 tín chỉ"),
                   ("T03", "PY202", "COURSE_COMPLETED", "PY101", None, "Đã đạt PY101"),
                   ("T04", "PY202", "COURSE_SCORE_MIN", "CS101", 7, "CS101 >= 7"),
                   ("T05", "PY203", "COURSE_SCORE_MIN", "PY101", 5, "PY101 >= 5"),
                   ("T06", "PY203", "ACCUMULATED_AVERAGE_MIN", None, 6, "TBTL >= 6")]
    for cid, code, kind, ref, threshold, quote in definitions:
        conditions.append({"id": cid, "course": code, "kind": kind, "reference": ref,
                           "threshold": threshold, "operator": ">=" if threshold is not None else "completed",
                           "quote": quote, "status": "SYNTHETIC_VERIFIED", "page": 1, "limitations": "Dữ liệu giả lập"})
    source = {"id": "TEST", "title": "Tài liệu giả lập kiểm thử v1", "issued_at": "2026-10-07",
              "effective_at": "2026-10-07", "published_at": "2026-10-07", "scope_text": "Môi trường kiểm thử giả lập, không phải TLU",
              "usability": "SYNTHETIC_ONLY", "locator": "Mục kiểm thử", "url": None, "file_url": None,
              "limitations": "Chỉ dùng kiểm thử phần mềm", "applicable": True, "cohorts": ["K37"]}
    paragraph = {"id": "TEST-REGISTRATION", "source_id": "TEST", "kind": "policy",
                 "text": "Quy định GIẢ LẬP: đăng ký tối đa 18 tín chỉ mỗi kỳ; cần kiểm tra tiên quyết từng môn.",
                 "page": 7, "section": "Điều giả lập 1", "cohort": "K37", "version": "sample-v1",
                 "verification": "SYNTHETIC_VERIFIED", "content_level": "synthetic_paragraph"}
    for name, obj in {"courses": courses, "conditions": conditions, "sources": [source], "gaps": [],
                      "raw_rows": [], "manifest": {"dataset": "sample", "cohort": "K37", "course_count": 6,
                      "snapshot_date": "2026-10-07", "amendments_verified": True,
                      "original_documents_ingested": False, "paragraphs": [paragraph]}}.items():
        (folder / (name + ".json")).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    create(Path(__file__).resolve().parents[1] / "data" / "sample")
