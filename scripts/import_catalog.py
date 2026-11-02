"""Rebuild runtime JSON from the CNTT K35–K39 workbook without inferring blank fields.

Each cohort keeps its own curriculum/version: K37 is the verified 2024 frame (S01), K36 is a
provisional extract from user-supplied page images (S26) that has not been matched to the
original decision, and K35/K38/K39 only have version/coverage records, never borrowed courses.

Requires openpyxl only for this import step; server/tests use the standard library.
"""
import argparse
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path

COHORTS = ('K35', 'K36', 'K37', 'K38', 'K39')
REQUIRED = ('Hoc phan', 'Dieu kien', 'Nguon', 'Can xac minh', 'Dong nguon', 'Khoa va phien ban',
            'Do day du', 'Can bo sung')
# Expected counts per cohort: courses, distinct codes, conditions, raw rows, blank prerequisite cells.
EXPECTED = {'K37': (99, 99, 76, 100, 31), 'K36': (72, 72, 82, 72, 17)}
# K37 keeps the identifiers already used by the evaluation set and citations.
VERSION = {'CNTT-2024': '24081902/2024'}
# Course-carrying bindings. K36 stays provisional until S26 is matched to S15.
BINDINGS = {
    'K37': dict(curriculum_id='CNTT-2024', status='VERIFIED_SNAPSHOT', source_id='S01', effective_from='2024-08-19',
                limitations='Khung gốc 2024; chưa xác minh đầy đủ sửa đổi sau 2024.'),
    'K36': dict(curriculum_id='CNTT-K36-ANH-20261102', status='PROVISIONAL_SNAPSHOT', source_id='S26', effective_from=None,
                limitations='Bảng học phần K36 trích từ ảnh khung trang 48–49 (S26) do người dùng cung cấp; '
                            'chưa đối chiếu với QĐ gốc 23082903 (S15), chưa có danh mục mã AD. Chỉ dùng tham khảo.'),
}
# One version paragraph per cohort, attached to the source that establishes that cohort's frame.
VERSION_SOURCE = {'K35': 'S13', 'K36': 'S15', 'K37': 'S01', 'K38': 'S17', 'K39': 'S20'}
KINDS = {'COURSE_SCORE': 'COURSE_SCORE_MIN', 'CREDITS_ACCUMULATED': 'ACCUMULATED_CREDITS_MIN',
         'CUMULATIVE_AVERAGE': 'ACCUMULATED_AVERAGE_MIN'}


def scalar(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def cohort_list(text):
    return [c for c in re.findall(r'K\d{2}', str(text or '')) if c in COHORTS]


def convert(workbook_path, destination, library_file_id=None):
    from openpyxl import load_workbook

    path, out = Path(workbook_path), Path(destination)
    workbook = load_workbook(path, data_only=True)
    if not all(name in workbook.sheetnames for name in REQUIRED):
        raise ValueError('Thiếu tab bắt buộc của workbook CNTT K35–K39: ' + ', '.join(REQUIRED))

    def table(sheet, header_row):
        values = list(workbook[sheet].values)
        return [(i, [scalar(v) for v in row]) for i, row in enumerate(values[header_row:], header_row + 1) if row[0]]

    sources = []
    for excel_row, row in table('Nguon', 4):
        (sid, title, issued, effective, published, scope, usability, locator, url, file_url, limitations,
         verified, conditional, checked, relation, version_code) = row[:16]
        cohorts = cohort_list(verified)
        scope_status = 'VERIFIED' if cohorts else 'UNVERIFIED'
        if sid == 'S26':
            # The user confirmed these images are the K36 frame; the decision number is still unmatched.
            cohorts, scope_status = ['K36'], 'USER_CONFIRMED_UNMATCHED'
        sources.append({
            'id': sid, 'title': title, 'issued_at': issued, 'effective_at': effective, 'published_at': published,
            'scope_text': scope, 'usability': usability, 'locator': locator, 'url': url, 'file_url': file_url,
            'limitations': limitations, 'conditional_scope': conditional or None, 'checked_at': checked,
            'relation': relation or None, 'version_code': version_code or None,
            'cohorts': cohorts, 'programs': ['CNTT'], 'scope_verified': bool(cohorts), 'scope_status': scope_status,
            'document_version': f"{sid}:{version_code or issued}",
            'effective_from': effective if re.match(r'\d{4}-\d{2}-\d{2}$', str(effective)) else None,
            'effective_to': None,
            # Only frames that carry course records pin a curriculum; shared documents apply by cohort.
            'curriculum_ids': [b['curriculum_id'] for b in BINDINGS.values() if b['source_id'] == sid],
            'content_level': 'inventory_summary', 'workbook_sheet': 'Nguon', 'workbook_row': excel_row})

    courses = []
    for excel_row, row in table('Hoc phan', 4):
        (code, name, credits, group, rule, prerequisite, status, page, hours, factor, row_count, source_rows,
         limitations, curriculum, cohort, source_id, image_page) = row[:17]
        courses.append({
            'code': code, 'name': name, 'credits': credits, 'group': group, 'selection_rule': rule,
            'prerequisite_raw': None if status == 'SOURCE_BLANK' else prerequisite, 'prerequisite_status': status,
            'page': page, 'image_page': image_page, 'hours': hours, 'factor': factor,
            'source_row_count': row_count, 'source_rows': source_rows, 'limitations': limitations,
            'source_id': source_id, 'cohort': cohort, 'program_id': 'CNTT', 'curriculum_id': curriculum,
            'version': VERSION.get(curriculum, curriculum),
            'verification': 'VERIFIED_TRANSCRIPTION' if cohort == 'K37' else 'IMAGE_TRANSCRIPTION_UNMATCHED',
            'current_amendments_verified': False, 'workbook_sheet': 'Hoc phan', 'workbook_row': excel_row})

    conditions = []
    for excel_row, row in table('Dieu kien', 4):
        (cid, course, kind, reference, operator, threshold, quote, status, page, limitations, curriculum, cohort,
         source_id, group, within, between, image_page) = row[:17]
        conditions.append({
            'id': cid, 'course': course, 'kind': KINDS.get(kind, kind), 'reference': reference,
            'operator': '>=' if operator in ('≥', '>=') else operator, 'threshold': threshold, 'quote': quote,
            'status': status, 'page': page, 'image_page': image_page, 'limitations': limitations,
            'group': group, 'within_group': within, 'between_groups': between,
            'program_id': 'CNTT', 'curriculum_id': curriculum, 'version': VERSION.get(curriculum, curriculum),
            'source_id': source_id, 'cohort': cohort, 'workbook_sheet': 'Dieu kien', 'workbook_row': excel_row})

    # Grouped sources (K36) become an explicit AND-of-groups tree; OR inside a group means "any one".
    for course in courses:
        own = [c for c in conditions if c['course'] == course['code'] and c['curriculum_id'] == course['curriculum_id']]
        if not any(c['group'] for c in own):
            continue
        groups = {}
        for c in own:
            groups.setdefault(c['group'], []).append(c)
        if any(c['between_groups'] not in (None, 'AND') for c in own):
            raise ValueError('Quan hệ giữa nhóm chưa hỗ trợ: ' + course['code'])
        course['rule'] = {'op': 'all', 'children': [
            {'op': 'any' if members[0]['within_group'] == 'OR' else 'all',
             'children': [{'condition': c['id']} for c in members]} for members in groups.values()]}

    raw_rows = [row for _, row in table('Dong nguon', 4)]
    for cohort, expected in EXPECTED.items():
        mine = [c for c in courses if c['cohort'] == cohort]
        found = (len(mine), len({c['code'] for c in mine}), sum(c['cohort'] == cohort for c in conditions),
                 sum(r[12] == cohort for r in raw_rows), sum(c['prerequisite_status'] == 'SOURCE_BLANK' for c in mine))
        if found != expected:
            raise ValueError(f'Snapshot {cohort} không khớp mốc {expected}: {found}')

    gaps = []
    for excel_row, row in table('Can xac minh', 4):
        gid, topic, status, details, needed = row[:5]
        gaps.append({'id': gid, 'topic': topic, 'status': status, 'details': details, 'needed_evidence': needed,
                     'cohorts': ['K36'] if str(gid).startswith('K36-') else ['K37'], 'programs': ['CNTT'],
                     'workbook_sheet': 'Can xac minh', 'workbook_row': excel_row})
    for excel_row, row in table('Can bo sung', 1):
        bid, cohorts, priority, topic, needed, reason, owner, status = row[:8]
        gaps.append({'id': bid, 'topic': topic, 'status': status, 'details': f'{reason} (ưu tiên {priority}; {owner})',
                     'needed_evidence': needed, 'cohorts': cohort_list(cohorts), 'programs': ['CNTT'],
                     'workbook_sheet': 'Can bo sung', 'workbook_row': excel_row})

    versions = {row[0]: (excel_row, row) for excel_row, row in table('Khoa va phien ban', 1)}
    coverage = {row[0]: row for _, row in table('Do day du', 1)}
    bindings, paragraphs = [], []
    for cohort in COHORTS:
        excel_row, v = versions[cohort]
        (_, year, school_year, curriculum, version_name, decision, effective, status, source_list, locator,
         credits, years, limits, image_set, image_status) = v[:15]
        c = coverage[cohort]
        known = BINDINGS.get(cohort)
        bindings.append({'cohort': cohort, 'program_id': 'CNTT',
                         'curriculum_id': known['curriculum_id'] if known else curriculum,
                         'version': VERSION.get(known['curriculum_id'], known['curriculum_id']) if known else None,
                         'status': known['status'] if known else 'UNVERIFIED',
                         'source_id': known['source_id'] if known else None,
                         'effective_from': known['effective_from'] if known else None, 'effective_to': None,
                         'frame_version': curriculum, 'admission_year': year,
                         'limitations': known['limitations'] if known else
                         f'Chưa chuẩn hóa bảng học phần {cohort}; chỉ tra được thông tin chương trình và văn bản đã xác minh phạm vi. {c[8]}'})
        text = (f'Chương trình CNTT {cohort}: tuyển sinh năm {year} (năm học {school_year}). Phiên bản {curriculum} — '
                f'{version_name}; quyết định {decision}; hiệu lực {effective}; trạng thái: {status}. '
                f'Tổng tín chỉ (không gồm GDQP/GDTC): {credits}; thời gian đào tạo: {years} năm. Giới hạn: {limits}. '
                f'Mức đầy đủ — khung/CTĐT: {c[2]}; bảng học phần: {c[3]}; tiên quyết/đề cương: {c[4]}; quy chế: {c[5]}; '
                f'chuẩn đầu ra/quy đổi: {c[6]}; sửa đổi/chuyển tiếp: {c[7]}. Mức dùng thực tế: {c[8]}')
        paragraphs.append({'id': 'VERSION-' + cohort, 'source_id': VERSION_SOURCE[cohort], 'kind': 'scope', 'text': text,
                           'page': None, 'section': f'Khoa va phien ban!{excel_row}', 'version': curriculum,
                           'verification': 'INVENTORY_CHECKED', 'content_level': 'inventory_summary',
                           'workbook_sheet': 'Khoa va phien ban', 'workbook_row': excel_row})

    out.mkdir(parents=True, exist_ok=True)
    payloads = {'sources': sources, 'courses': courses, 'conditions': conditions, 'gaps': gaps,
                'raw_rows': raw_rows, 'programs': bindings,
                'workbook_snapshot': {s.title: {'records': [{'excel_row': i, 'values': [scalar(v) for v in row]}
                                                            for i, row in enumerate(s.values, 1) if any(row)]}
                                      for s in workbook}}
    for name, data in payloads.items():
        (out / f'{name}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {'dataset': 'project', 'program': 'CNTT', 'schema_version': 3, 'snapshot_date': '2026-11-02',
                'workbook': path.name, 'workbook_sha256': digest, 'source_library_id': library_file_id,
                'tabs_present': workbook.sheetnames, 'source_count': len(sources),
                'supported_cohorts': list(COHORTS), 'verified_course_cohorts': ['K37'],
                'provisional_course_cohorts': ['K36'],
                'counts': {cohort: dict(zip(('courses', 'codes', 'conditions', 'raw_rows', 'source_blank'), expected))
                           for cohort, expected in EXPECTED.items()},
                'course_count': len(courses), 'raw_row_count': len(raw_rows), 'condition_count': len(conditions),
                'original_documents_ingested': False, 'amendments_verified': False,
                'provenance_note': 'Workbook CNTT K35–K39 cập nhật 02/11/2026. K37 giữ nguyên khung gốc S01; '
                                   'K36 trích từ ảnh S26 chưa đối chiếu QĐ gốc; K35/K38/K39 chưa có bảng học phần.',
                'paragraphs': paragraphs}
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return {k: v for k, v in manifest.items() if k != 'paragraphs'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('workbook')
    parser.add_argument('--output', default='data/project')
    parser.add_argument('--library-file-id', default=None)
    args = parser.parse_args()
    print(json.dumps(convert(args.workbook, args.output, args.library_file_id), ensure_ascii=False))
