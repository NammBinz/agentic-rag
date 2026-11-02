"""Fail-closed cohort/curriculum views over a shared, versioned evidence store."""
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_COHORTS = ('K35', 'K36', 'K37', 'K38', 'K39')
# A provisional snapshot (e.g. K36 from user-supplied images) is usable but always carries its caveat.
SNAPSHOT_STATUS = {'VERIFIED_SNAPSHOT': 'verified_snapshot', 'PROVISIONAL_SNAPSHOT': 'provisional_snapshot'}
USABLE = set(SNAPSHOT_STATUS.values())


def normalize(text):
    text = unicodedata.normalize('NFD', text.lower().replace('đ', 'd'))
    return ''.join(c for c in text if unicodedata.category(c) != 'Mn')


# Other programs named after "ngành"; group labels such as "bắt buộc ngành" never match.
OTHER_PROGRAMS = ('tri tue nhan tao', 'khoa hoc may tinh', 'he thong thong tin', 'mang may tinh',
                  'an toan thong tin', 'ky thuat phan mem', 'khoa hoc du lieu', 'ngon ngu', 'ke toan',
                  'quan tri', 'tai chinh', 'marketing', 'kinh te', 'luat', 'dieu duong', 'dinh duong',
                  'y te cong cong', 'cong tac xa hoi', 'viet nam hoc', 'du lich', 'logistics',
                  'thiet ke do hoa', 'truyen thong', 'toan ung dung', 'am nhac', 'thanh nhac')


def mentions_other_program(text):
    return any(re.search(r'\bnganh ' + program + r'\b', normalize(text)) for program in OTHER_PROGRAMS)


def course_codes(text):
    return list(dict.fromkeys(re.findall(r'\b[A-Z]{2}\d{3}\b', text.upper())))


class Catalog:
    def __init__(self, dataset='project', data_root=None, cohort='K37'):
        if dataset not in ('project', 'sample'):
            raise ValueError('dataset phải là project hoặc sample')
        if cohort is not None and not isinstance(cohort, str):
            raise ValueError('cohort phải là chuỗi hoặc null')
        self.dataset, self.cohort, self.data_root = dataset, cohort, data_root
        folder = (Path(data_root) if data_root else ROOT / 'data') / dataset
        def read(name):
            return json.loads((folder / f'{name}.json').read_text(encoding='utf-8'))
        self.manifest = read('manifest')
        self.sources = {s['id']: s for s in read('sources')}
        self.bindings = read('programs')
        self.context = self._resolve()
        self.courses = {}
        self.issues = []
        for record in read('courses'):
            if not self._record_matches(record) or not self.source_applies(self.sources.get(record['source_id'], {})):
                continue
            if record['code'] in self.courses:
                self.issues.append('Mã môn trùng trong cùng phiên bản: ' + record['code'])
            self.courses[record['code']] = {**record, 'cohort': cohort}
        # A conflicting record is not silently replaced by the last row.
        if self.issues:
            self.context.update(status='ambiguous', message='; '.join(self.issues))
            self.courses = {}
        self.conditions = [r for r in read('conditions') if self._record_matches(r)
                           and self.source_applies(self.sources.get(r.get('source_id'), {}))]
        self.gaps = [g for g in read('gaps') if cohort in g.get('cohorts', []) and 'CNTT' in g.get('programs', [])]
        self.chunks = self._chunks()
        ids = [c['id'] for c in self.chunks]
        if len(ids) != len(set(ids)):
            raise ValueError('Mã đoạn nguồn trùng trong cùng phạm vi')
        serialized = json.dumps([self.manifest, self.sources, self.bindings, self.context,
                                 self.chunks, self.conditions], sort_keys=True, ensure_ascii=False)
        self.fingerprint = hashlib.sha256(serialized.encode()).hexdigest()

    def for_cohort(self, cohort):
        return self if cohort == self.cohort else Catalog(self.dataset, self.data_root, cohort)

    def _active(self, item):
        day = self.manifest['snapshot_date']
        start, end = item.get('effective_from'), item.get('effective_to')
        return (not start or start <= day) and (not end or day < end)

    def _resolve(self):
        context = {'cohort': self.cohort, 'program_id': 'CNTT', 'curriculum_id': None,
                   'curriculum_version': None, 'as_of': self.manifest['snapshot_date']}
        if not self.cohort:
            return {**context, 'status': 'needs_input', 'message': 'Bạn thuộc khóa nào? Chọn K35–K39.'}
        if self.cohort not in SUPPORTED_COHORTS:
            return {**context, 'status': 'out_of_scope', 'message': 'Prototype hiện hỗ trợ lựa chọn K35–K39 ngành CNTT.'}
        candidates = [b for b in self.bindings if b.get('cohort') == self.cohort and b.get('program_id') == 'CNTT'
                      and b.get('status') in SNAPSHOT_STATUS and self._active(b)]
        if len(candidates) != 1:
            known = next((b for b in self.bindings if b.get('cohort') == self.cohort and b.get('program_id') == 'CNTT'), {})
            return {**context, 'status': 'ambiguous' if candidates else 'insufficient_data',
                    'frame_version': known.get('frame_version'),
                    'message': ('Có nhiều phiên bản cùng áp dụng; cần xác minh chương trình của người học.' if candidates else
                                known.get('limitations') or
                                f'Chưa có ánh xạ chương trình/phiên bản đã xác minh cho CNTT {self.cohort}. Không mượn khung khóa khác.')}
        binding = candidates[0]
        if not binding.get('curriculum_id') or not binding.get('version') or not binding.get('source_id'):
            return {**context, 'status': 'insufficient_data', 'message': 'Ánh xạ thiếu chương trình, phiên bản hoặc căn cứ nguồn.'}
        source = self.sources.get(binding['source_id'], {})
        if (not source.get('scope_verified') or self.cohort not in source.get('cohorts', [])
                or 'CNTT' not in source.get('programs', []) or not self._active(source)
                or not source.get('document_version')
                or (source.get('curriculum_ids') and binding['curriculum_id'] not in source['curriculum_ids'])):
            return {**context, 'status': 'insufficient_data', 'message': 'Nguồn ánh xạ không đủ căn cứ áp dụng đúng khóa/chương trình.'}
        return {**context, 'status': SNAPSHOT_STATUS[binding['status']], 'curriculum_id': binding['curriculum_id'],
                'curriculum_version': binding['version'], 'binding_source_id': binding['source_id'],
                'message': binding.get('limitations') or 'Dùng đúng chương trình trong snapshot đã kiểm chứng.'}

    def source_applies(self, source):
        if not self.cohort or self.cohort not in SUPPORTED_COHORTS or not source.get('scope_verified'):
            return False
        if self.cohort not in source.get('cohorts', []) or 'CNTT' not in source.get('programs', []):
            return False
        if not source.get('document_version') or not self._active(source):
            return False
        curricula = source.get('curriculum_ids')
        return not curricula or (self.usable and self.context['curriculum_id'] in curricula)

    def _record_matches(self, record):
        return (self.usable and record.get('program_id') == 'CNTT'
                and record.get('curriculum_id') == self.context['curriculum_id']
                and record.get('version') == self.context['curriculum_version'])

    @property
    def usable(self):
        return self.context['status'] in USABLE

    def course_chunk_id(self, course):
        return course.get('chunk_id', 'COURSE-' + course['code'])

    def _metadata(self, source_id, kind, **extra):
        source = self.sources.get(source_id, {})
        return {'source_id': source_id, 'kind': kind, 'cohort': self.cohort,
                'program_id': 'CNTT', 'curriculum_id': self.context['curriculum_id'],
                'curriculum_version': self.context['curriculum_version'],
                'applicable_cohorts': source.get('cohorts', [self.cohort]),
                'document_version': source.get('document_version'), **extra}

    def _chunks(self):
        chunks = []
        for course in self.courses.values():
            raw = course['prerequisite_raw']
            text = (f"{course['code']} — {course['name']}. Tín chỉ: {course['credits']}. "
                    f"Nhóm: {course['group']}. Quy tắc lựa chọn: {course['selection_rule']}. "
                    f"Tiên quyết ghi trong nguồn: {raw if raw is not None else 'ô trống; chưa xác định'}.")
            if course.get('limitations'):
                text += ' ' + course['limitations']
            if course.get('image_page'):
                text += f" Vị trí: ảnh trang {course['image_page']}."

            chunks.append(self._metadata(course['source_id'], 'course', id=self.course_chunk_id(course),
                          course_code=course['code'], text=text, page=course['page'],
                          section=course.get('source_rows', course['code']), version=course['version'],
                          verification=course['verification'], content_level='transcribed_row',
                          workbook_sheet=course.get('workbook_sheet'), workbook_row=course.get('workbook_row')))
        for source in self.sources.values():
            if not self.source_applies(source):
                continue
            text = (f"{source['title']}. Phạm vi: {source['scope_text']}. "
                    f"Hiệu lực: {source['effective_at']}. {source['limitations']}")
            chunks.append(self._metadata(source['id'], 'scope', id='SOURCE-' + source['id'], text=text,
                          page=None, section=source['locator'], version=source['document_version'],
                          verification='INVENTORY_CHECKED', content_level='inventory_summary'))
        if self.cohort in SUPPORTED_COHORTS and not self.usable:
            chunks.append(self._metadata('INVENTORY', 'gap', id='GAP-CONTEXT-' + self.cohort,
                          text=self.context['message'], page=None, section='Ánh xạ khóa–chương trình',
                          version='schema-v2', verification='MISSING_OR_UNVERIFIED', content_level='inventory_summary'))
        for gap in self.gaps:
            chunks.append(self._metadata('INVENTORY', 'gap', id='GAP-' + gap['id'],
                          text=f"{gap['topic']}: {gap['details']} Cần bổ sung: {gap['needed_evidence']}",
                          page=None, section=gap['id'], version='schema-v2',
                          verification='MISSING_OR_UNVERIFIED', content_level='inventory_summary'))
        for chunk in self.manifest.get('paragraphs', []):
            if self.source_applies(self.sources.get(chunk['source_id'], {})):
                chunks.append(self._metadata(chunk['source_id'], chunk['kind'], **{k: v for k, v in chunk.items()
                              if k not in ('cohort', 'program_id', 'curriculum_id', 'curriculum_version',
                                           'applicable_cohorts', 'document_version', 'source_id', 'kind')}))
        return chunks

    def citation(self, chunk):
        source = self.sources.get(chunk['source_id'], {})
        return {**chunk, 'source_title': source.get('title', 'Danh mục dữ liệu — mục cần xác minh'),
                'url': source.get('url'), 'file_url': source.get('file_url'),
                'effective_at': source.get('effective_at'), 'source_scope': source.get('scope_text'),
                'dataset': self.dataset,
                'evidence_note': ('Dữ liệu giả lập, không phải quy định TLU.' if self.dataset == 'sample' else
                                  'Trích từ ảnh khung do người dùng cung cấp; chưa đối chiếu với quyết định gốc.'
                                  if chunk.get('verification') == 'IMAGE_TRANSCRIPTION_UNMATCHED' else
                                  'Trích đoạn bảng chuẩn hóa/danh mục; chưa nhập toàn văn PDF gốc.')}

    def select_courses(self, query):
        code = query.strip().upper()
        if code in self.courses:
            return [self.courses[code]]
        terms = normalize(query).split()
        if not terms:
            return []
        return [c for c in self.courses.values() if all(t in normalize(c['name'] + ' ' + c['code']) for t in terms)]
