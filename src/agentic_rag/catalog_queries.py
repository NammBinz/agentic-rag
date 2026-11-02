"""Resolve scoped catalog reporting queries without treating top-k hits as a census."""
import re
from .catalog import course_codes, normalize, mentions_other_program

GROUPS = {
    'dai cuong': 'Đại cương',
    'co so khoi nganh': 'Cơ sở khối ngành',
    'co so nganh': 'Cơ sở khối ngành',
    'bat buoc nganh': 'Bắt buộc ngành',
    'lua chon nganh': 'Lựa chọn ngành',
    'lua chon tu do': 'Lựa chọn tự do AD',
}


def _explicit(question, catalog):
    text = normalize(question)
    if course_codes(question) or any(normalize(c['name']) in text for c in catalog.courses.values()):
        return None
    course_word = bool(re.search(r'\b(mon|hoc phan)\b', text))
    listing = any(w in text for w in ('nhung mon', 'cac mon', 'mon nao', 'mon gi', 'danh sach', 'liet ke', 'danh muc', 'nhung hoc phan', 'cac hoc phan', 'gom nhung gi'))
    listing = listing or bool(re.search(r'(tat ca|toan bo) (mon|hoc phan)', text))
    counting = bool(re.search(r'(bao nhieu|may|so luong|tong so) (mon|hoc phan)', text))
    whole_program = any(w in text for w in ('chuong trinh', 'nganh', 'cntt', 'toan bo', 'toan khoa', 'tat ca', 'k37'))
    group = next((value for marker, value in GROUPS.items() if marker in text), None)
    optional = any(w in text for w in ('tu chon', 'lua chon', 'thay the'))
    mandatory = 'bat buoc' in text
    if not (course_word and (listing or counting) and (whole_program or group or optional or mandatory)):
        return None
    # A question about individual prerequisites is not an inventory query.
    if any(w in text for w in ('tien quyet', 'yeu cau mon', 'du dieu kien', 'dang ky', 'hoc phi', 'si so', 'lich hoc', 'thoi khoa bieu', 'mien hoc', 'tot nghiep', 'toeic')):
        return None
    subset = 'mandatory' if mandatory and not optional else 'choices' if optional and not group else 'all'
    return {'subset': subset, 'group': group, 'count_only': counting and not listing}


LIST_FOLLOWUPS = {'la nhung mon gi', 'nhung mon nao', 'la nhung mon nao',
                  'gom nhung mon nao', 'ke ten cac mon', 'liet ke di', 'liet ke',
                  'danh sach dau', 'cu the la nhung mon gi'}


def _followup(text):
    if text in LIST_FOLLOWUPS:
        return 'list'
    if re.fullmatch(r'(?:(?:vay|co|tong cong|tong)\s+)*(?:bao nhieu|may) (?:mon|hoc phan)(?: hoc)?(?: tat ca| bat buoc)?', text):
        return 'count'
    return None


def catalog_query(question, catalog, history=None):
    """Resolve generic count/list follow-ups only while the catalog topic remains active."""
    text = normalize(question).strip(' ?.!')
    explicit = _explicit(question, catalog)
    if explicit:
        return explicit
    kind = _followup(text)
    if not kind:
        return None
    for entry in reversed((history or [])[-6:]):
        previous = entry.get('question', '')
        prev = normalize(previous).strip(' ?.!')
        cohorts = set(re.findall(r'\bk\s*(\d{2,3})\b', prev)) | set(re.findall(r'khoa\s+(\d{2,3})\b', prev))
        versions = set(re.findall(r'cntt[- ]?(20\d{2})', prev))
        current = catalog.context.get('curriculum_id') or ''
        if (cohorts - {str(catalog.cohort or '').lstrip('K')} or
                (versions and any('CNTT-' + v != current for v in versions)) or
                mentions_other_program(previous)):
            break
        resolved = _explicit(previous, catalog)
        if resolved:
            return {**resolved, 'count_only': kind == 'count', 'resolved_from': previous}
        if not _followup(prev):
            break
    return {'needs_context': True, 'count_only': kind == 'count'}
