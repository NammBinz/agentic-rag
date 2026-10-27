"""Inspectable routing decisions, not hidden model reasoning."""
from .catalog import course_codes, normalize
from .catalog_queries import catalog_query


def plan(question, catalog, intent=None, target_course=None, history=None):
    if intent not in (None, "lookup", "prerequisites", "conditions"):
        raise ValueError("intent phải là lookup, conditions hoặc prerequisites")
    inventory = catalog_query(question, catalog, history) if intent is None and not target_course else None
    if inventory:
        return {'intent': 'catalog_summary', 'targets': [], 'resolved_question': question,
                'source_ids': None, 'missing_topic': None, 'trace_depth': 0,
                'needs_target': False, 'catalog_query': inventory, 'router': 'deterministic-v1'}
    resolved = question
    if history and not course_codes(question) and any(p in normalize(question) for p in ("mon do", "hoc phan do")):
        for entry in reversed(history[-6:]):
            codes = course_codes(entry.get("question", ""))
            if len(codes) == 1:
                resolved += " " + codes[0]
                break
    targets = course_codes(target_course) if target_course else course_codes(resolved)
    if not targets:
        # Full exact course names can be resolved without asking users to know the code.
        normalized = normalize(resolved)
        targets = [c["code"] for c in catalog.courses.values() if normalize(c["name"]) in normalized]
    text = normalize(resolved)
    needs_check = intent == "prerequisites" or (bool(targets) and any(w in text for w in
                  ("kiem tra tien quyet", "dang ky", "du dieu kien", "co the hoc", "da dat", "da hoc")))
    inspect = intent == 'conditions' or (any(w in text for w in
        ('tien quyet', 'yeu cau mon', 'mon nao', 'chuoi', 'yeu cau gi')) or (bool(targets) and 'dieu kien' in text))
    selected_intent = ('prerequisites' if needs_check else 'conditions' if inspect else
                       'lookup' if targets or intent == 'lookup' else 'qa')
    trace_depth = 2 if any(w in text for w in ('chuoi', 'mon do', 'mon nay yeu cau', 'lien quan')) else 0
    # "Can I take X after Y?" has one target; other IDs remain evidence requirements.
    if needs_check and not target_course and len(targets) > 1:
        markers = ("dang ky", "tien quyet", "co the hoc")
        candidates = []
        for marker in markers:
            pos = text.find(marker)
            if pos >= 0:
                candidates = course_codes(resolved[pos:])
                if candidates:
                    break
        if candidates:
            targets = candidates[:1]
    source_ids = None
    if selected_intent == "qa" and catalog.dataset == "project":
        if "toeic" in text:
            source_ids = ["S04", "INVENTORY"]
        elif "chuong trinh" in text or "khung" in text or "nam tuyen sinh" in text:
            source_ids = ["S01", "S02", "INVENTORY"]
        elif "quy che" in text:
            source_ids = ["S03", "INVENTORY"]
    missing_topic = None
    if catalog.dataset == "project":
        checks = (("hoc phi", "Chưa có nguồn học phí theo học kỳ."),
                  ("si so", "Chưa có dữ liệu sĩ số/lớp mở hiện thời."),
                  ("lich hoc", "Chưa có dữ liệu lịch học hiện thời."),
                  ("thoi khoa bieu", "Chưa có dữ liệu thời khóa biểu hiện thời."),
                  ("han dang ky", "Chưa có thông báo hạn đăng ký theo học kỳ."),
                  ("mien hoc", "Chưa có quy định miễn học đúng phiên bản đúng khóa."),
                  ("tot nghiep", "Chưa có bộ điều kiện xét tốt nghiệp đầy đủ."))
        for marker, message in checks:
            if marker in text:
                missing_topic = message
                break
        if "toeic" in text and any(m in text for m in ("diem", "bao nhieu", "nguong")):
            missing_topic = "Danh mục xác minh phạm vi TOEIC K36–K37, nhưng chưa nhập ngưỡng điểm từ toàn văn."
    return {"intent": selected_intent, "targets": targets, "resolved_question": resolved,
            "source_ids": source_ids, "missing_topic": missing_topic,
            "trace_depth": trace_depth,
            "needs_target": selected_intent in ("lookup", "prerequisites", "conditions") and not targets,
            "router": "deterministic-v1"}


def missing_evidence(question, targets, chunks, catalog, include_dependencies=False):
    """One bounded expansion: requested records + immediate prerequisite references."""
    present = {c["id"] for c in chunks}
    requested = list(dict.fromkeys(course_codes(question) + targets))
    missing = [code for code in requested if code in catalog.courses and catalog.course_chunk_id(catalog.courses[code]) not in present]
    for target in targets if include_dependencies else []:
        course = catalog.courses.get(target)
        if not course:
            continue
        for code in course_codes(course["prerequisite_raw"] or ""):
            if code in catalog.courses and catalog.course_chunk_id(catalog.courses[code]) not in present and code not in missing:
                missing.append(code)
    return missing
