"""Cross-cohort isolation and evidence eligibility regression tests."""
import json
import tempfile
import shutil
import unittest
from pathlib import Path
from agentic_rag.catalog import Catalog, ROOT
from agentic_rag.engine import Engine
from agentic_rag.tools import AcademicTools
from agentic_rag.retrieval import Retriever
from agentic_rag.provider import Settings

class ScopeTests(unittest.TestCase):
    def test_same_code_has_distinct_versions_and_credits(self):
        for cohort, credits, version in [('K35', 3, 'sample-v1'), ('K36', 3, 'sample-v1'), ('K37', 3, 'sample-v1'), ('K38', 4, 'sample-v2')]:
            catalog = Catalog('sample', cohort=cohort)
            self.assertEqual(catalog.courses['PY201']['credits'], credits)
            self.assertEqual(catalog.context['curriculum_version'], version)
            chunks, _ = Retriever(catalog, Settings()).search('PY201', cohort)
            self.assertEqual(chunks[0]['version'], version)
            self.assertTrue(all(c['cohort'] == cohort for c in chunks))

    def test_tools_use_selected_threshold(self):
        tools = AcademicTools(Catalog('sample'))
        profile = {'completed': ['PY101'], 'credits': 12}
        self.assertEqual(tools.prerequisites('PY201', 'K37', profile)['status'], 'satisfied_in_snapshot')
        self.assertEqual(tools.prerequisites('PY201', 'K38', profile)['status'], 'not_met_in_snapshot')
        self.assertEqual(tools.lookup('PY201', 'K38')['courses'][0]['credits'], 4)

    def test_shared_document_stored_once_and_usable_without_curriculum(self):
        catalog = Catalog('sample', cohort='K39')
        self.assertEqual(catalog.courses, {})
        self.assertEqual(sum(s['id'] == 'TEST-COMMON' for s in catalog.sources.values()), 1)
        r = Engine('sample').answer('Đăng ký tối đa bao nhiêu tín chỉ mỗi kỳ?', cohort='K39')
        citation = next(c for c in r['citations'] if c['id'] == 'TEST-REGISTRATION')
        self.assertEqual(len(citation['applicable_cohorts']), 5)
        self.assertEqual(citation['document_version'], 'common-v1')

    def test_missing_curriculum_never_borrows_project_courses(self):
        for cohort in ('K35', 'K38', 'K39'):
            e = Engine(cohort=cohort)
            self.assertEqual(e.catalog.courses, {})
            for mode in ('rag', 'agent'):
                r = e.answer('IT320', mode=mode, cohort=cohort)
                self.assertEqual(r['status'], 'insufficient_data')
                self.assertEqual(r['metrics']['retrieval_rounds'], 0)
                self.assertEqual(r['citations'], [])

    def test_real_common_source_only_for_reviewed_cohorts(self):
        for cohort in ('K35', 'K36', 'K37', 'K38', 'K39'):
            c = Catalog(cohort=cohort)
            self.assertEqual(any(x['source_id'] == 'S04' for x in c.chunks), cohort in ('K36', 'K37'))

    def test_missing_or_conflicting_cohort(self):
        e = Engine('sample')
        self.assertEqual(e.answer('PY201')['status'], 'needs_input')
        self.assertEqual(e.answer('PY201 của K37', cohort='K38')['status'], 'needs_input')

    def test_cache_fingerprint_scoped(self):
        catalogs = [Catalog('sample', cohort=c) for c in ('K35', 'K37', 'K38')]
        self.assertEqual(len({c.fingerprint for c in catalogs}), 3)

    def test_expired_unverified_and_conflicting_versions_block_courses(self):
        for change in ('expired', 'unverified', 'ambiguous', 'bad-source'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as root:
                folder = Path(root) / 'sample'
                shutil.copytree(ROOT / 'data' / 'sample', folder)
                bindings = json.loads((folder / 'programs.json').read_text())
                b = next(b for b in bindings if b['cohort'] == 'K37')
                if change == 'expired': b['effective_to'] = '2026-10-14'
                if change == 'unverified': b['status'] = 'UNVERIFIED'
                if change == 'ambiguous': bindings.append(dict(b))
                if change == 'bad-source': b['source_id'] = 'MISSING'
                (folder / 'programs.json').write_text(json.dumps(bindings))
                c = Catalog('sample', data_root=root)
                self.assertEqual(c.courses, {})
                self.assertEqual(AcademicTools(c).lookup('PY201', 'K37')['status'], 'insufficient_data')

    def test_api_catalog_and_chunks_require_scope(self):
        # Reuse HTTP test helpers without inheriting/rerunning their tests.
        server = __import__('agentic_rag.server', fromlist=['create_server']).create_server(port=0, settings=Settings(), demo_only=False)
        import threading, urllib.request, urllib.error
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = 'http://127.0.0.1:' + str(server.server_port)
        try:
            def get(path):
                with urllib.request.urlopen(base + path) as r: return json.load(r)
            self.assertEqual(get('/api/catalog?dataset=sample&cohort=K38')['courses'][2]['credits'], 4)
            self.assertEqual(get('/api/catalog?cohort=K38')['courses'], [])
            self.assertEqual(get('/api/catalog')['context']['status'], 'needs_input')
            with self.assertRaises(urllib.error.HTTPError) as cm:
                get('/api/chunks/COURSE-PY201?dataset=sample&cohort=K38')
            self.assertEqual(cm.exception.code, 404)
            self.assertEqual(get('/api/chunks/COURSE-PY201-V2?dataset=sample&cohort=K38')['curriculum_version'], 'sample-v2')
        finally:
            server.shutdown(); server.server_close(); thread.join(2)


class ProgramScopeTests(unittest.TestCase):
    def test_other_program_is_refused_before_retrieval(self):
        engine = Engine('project', Settings(), cohort='K37')
        for question in ['Ngành Ngôn ngữ Anh K37 có bao nhiêu môn bắt buộc?',
                         'Ngành Kế toán có học IT320 không?', 'ngành trí tuệ nhân tạo có những môn nào?']:
            with self.subTest(question=question):
                result = engine.answer(question, mode='agent', cohort='K37')
                self.assertEqual(result['status'], 'out_of_scope')
                self.assertEqual(result['metrics']['retrieval_rounds'], 0)

    def test_cntt_and_group_labels_are_not_other_programs(self):
        engine = Engine('project', Settings(), cohort='K37')
        for question in ['Ngành CNTT K37 có bao nhiêu môn bắt buộc?', 'Nhóm bắt buộc ngành có bao nhiêu học phần?',
                         'Ngành công nghệ thông tin có môn IT320 không?']:
            with self.subTest(question=question):
                self.assertNotEqual(engine.answer(question, mode='agent', cohort='K37')['status'], 'out_of_scope')
