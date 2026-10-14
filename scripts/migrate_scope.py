"""Upgrade reviewed K37 snapshot metadata; never invent courses for other cohorts."""
import json
from pathlib import Path


def upgrade(folder):
    folder = Path(folder)
    def read(name):
        return json.loads((folder / (name + '.json')).read_text(encoding='utf-8'))
    def write(name, value):
        (folder / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    identity = {'program_id': 'CNTT', 'curriculum_id': 'CNTT-2024', 'version': '24081902/2024'}
    for name in ('courses', 'conditions'):
        records = read(name)
        for r in records:
            r.update(identity)
            if name == 'conditions':
                r['source_id'] = 'S01'
        write(name, records)
    sources = read('sources')
    for s in sources:
        # S04 already states K36–K37 explicitly in the reviewed workbook.
        s['cohorts'] = ['K36', 'K37'] if s['id'] == 'S04' else (['K38'] if s['id'] == 'S12' else (['K37'] if s['id'] in ('S01', 'S02', 'S03') else []))
        s['programs'] = ['CNTT']
        s['scope_verified'] = bool(s['cohorts'])
        s['document_version'] = s['id'] + ':' + str(s['issued_at'])
        s['effective_from'] = s['effective_at'] if str(s['effective_at'])[:4].isdigit() else None
        s['effective_to'] = None
        s['curriculum_ids'] = ['CNTT-2024'] if s['id'] == 'S01' else []
    write('sources', sources)
    gaps = read('gaps')
    for g in gaps:
        g.update(cohorts=['K37'], programs=['CNTT'])
    write('gaps', gaps)
    bindings = []
    for cohort in ('K35', 'K36', 'K37', 'K38', 'K39'):
        b = {'cohort': cohort, 'program_id': 'CNTT', 'curriculum_id': None, 'version': None,
             'status': 'UNVERIFIED', 'source_id': None, 'effective_from': None, 'effective_to': None,
             'limitations': 'Chưa thu thập/xác minh ánh xạ chương trình, học phần và quy định đúng khóa.'}
        if cohort == 'K37':
            b.update(identity, status='VERIFIED_SNAPSHOT', source_id='S01', effective_from='2024-08-19',
                     limitations='Khung gốc 2024; chưa xác minh đầy đủ sửa đổi sau 2024.')
        bindings.append(b)
    write('programs', bindings)
    manifest = read('manifest')
    manifest.update(schema_version=2, supported_cohorts=['K35', 'K36', 'K37', 'K38', 'K39'],
                    verified_course_cohorts=['K37'])
    write('manifest', manifest)


if __name__ == '__main__':
    upgrade(Path(__file__).resolve().parents[1] / 'data' / 'project')
