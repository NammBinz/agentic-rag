"""Cohort-first demo: K37 verified, K36 provisional from images, K35/K38/K39 version-only."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from agentic_rag.catalog import Catalog, ROOT
from agentic_rag.provider import Settings
from agentic_rag.server import create_app
from agentic_rag.tools import AcademicTools

WORKBOOK = ROOT / 'data' / 'input' / 'CNTT_K35-K39_nguon_phien_ban.xlsx'


class CohortSelectionTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app(Settings()).test_client()

    def chat(self, question, cohort, **extra):
        return self.client.post('/api/chat', json={'question': question, 'cohort': cohort, **extra}).json

    def test_picker_lists_each_cohort_with_its_coverage(self):
        items = {c['cohort']: c for c in self.client.get('/api/cohorts').json['cohorts']}
        self.assertEqual(list(items), ['K35', 'K36', 'K37', 'K38', 'K39'])
        self.assertEqual((items['K37']['status'], items['K37']['course_count']), ('verified_snapshot', 99))
        self.assertEqual((items['K36']['status'], items['K36']['course_count']), ('provisional_snapshot', 72))
        self.assertEqual(items['K36']['frame_version'], 'CNTT-2023')
        for cohort in ('K35', 'K38', 'K39'):
            self.assertEqual((items[cohort]['status'], items[cohort]['course_count']), ('insufficient_data', 0))

    def test_no_cohort_means_no_retrieval(self):
        r = self.client.post('/api/chat', json={'question': 'IT320 mấy tín chỉ?'}).json
        self.assertEqual(r['status'], 'needs_input')
        self.assertEqual(r['metrics']['retrieval_rounds'], 0)

    def test_each_cohort_uses_its_own_records(self):
        k36 = self.chat('MI201 yêu cầu tiên quyết gì?', 'K36')
        k37 = self.chat('MI201 yêu cầu tiên quyết gì?', 'K37')
        self.assertIn('CS122', k36['answer'])
        self.assertIn('CS121', k37['answer'])
        self.assertTrue(all(c['cohort'] == 'K36' for c in k36['citations']))
        self.assertIn('chưa đối chiếu', k36['citations'][0]['evidence_note'])
        self.assertIn('chưa đối chiếu', k36['notice'])

    def test_other_cohort_or_version_in_question_is_refused(self):
        for question, cohort in [('K37 học IT320 mấy tín?', 'K36'), ('IT320 theo CNTT-2024', 'K36'),
                                 ('khóa 36 thì sao?', 'K37')]:
            with self.subTest(question=question):
                r = self.chat(question, cohort)
                self.assertEqual(r['status'], 'out_of_scope')
                self.assertEqual(r['metrics']['retrieval_rounds'], 0)
        self.assertNotEqual(self.chat('IT320 trong CNTT-2023', 'K36')['status'], 'out_of_scope')

    def test_version_only_cohorts_answer_from_program_records(self):
        r = self.chat('Chương trình CNTT K38 có bao nhiêu tín chỉ, học mấy năm?', 'K38', mode='rag')
        self.assertIn('VERSION-K38', [c['id'] for c in r['citations']])
        self.assertTrue(all(c['cohort'] == 'K38' for c in r['citations']))
        self.assertEqual(self.chat('IT320 mấy tín chỉ?', 'K38')['status'], 'insufficient_data')


class K36RuleTests(unittest.TestCase):
    def setUp(self):
        self.tools = AcademicTools(Catalog('project', None, 'K36'))

    def check(self, code, profile):
        return self.tools.prerequisites(code, 'K36', profile)['status']

    def test_and_of_groups_with_thresholds(self):
        self.assertEqual(self.check('IT320', {'grades': {'CS122': 5}, 'credits': 50}), 'satisfied_in_snapshot')
        self.assertEqual(self.check('IT320', {'grades': {'CS122': 5}, 'credits': 40}), 'not_met_in_snapshot')
        self.assertEqual(self.check('IT320', {'grades': {'CS122': 3}, 'credits': 50}), 'not_met_in_snapshot')

    def test_or_group_is_kept_as_any_of(self):
        rule = Catalog('project', None, 'K36').courses['CS320']['rule']
        self.assertEqual(rule['op'], 'all')
        self.assertEqual([g['op'] for g in rule['children']], ['any', 'any'])
        self.assertEqual(len(rule['children'][0]['children']), 3)

    def test_blank_cells_stay_unknown(self):
        catalog = Catalog('project', None, 'K36')
        blank = [c for c in catalog.courses.values() if c['prerequisite_status'] == 'SOURCE_BLANK']
        self.assertEqual(len(blank), 17)
        self.assertTrue(all(c['prerequisite_raw'] is None for c in blank))


@unittest.skipUnless(importlib.util.find_spec('openpyxl') and WORKBOOK.exists(), 'openpyxl hoặc workbook chưa có')
class ImportReproducibilityTests(unittest.TestCase):
    def test_import_reproduces_committed_snapshot(self):
        spec = importlib.util.spec_from_file_location('import_catalog', ROOT / 'scripts' / 'import_catalog.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            module.convert(WORKBOOK, folder)
            for name in ('courses', 'conditions', 'sources', 'programs', 'gaps'):
                with self.subTest(name=name):
                    fresh = json.loads((Path(folder) / f'{name}.json').read_text(encoding='utf-8'))
                    stored = json.loads((ROOT / 'data' / 'project' / f'{name}.json').read_text(encoding='utf-8'))
                    self.assertEqual(fresh, stored)


class DocumentScopeTests(unittest.TestCase):
    """Full-text regulations, tuition and language rules reach only the cohorts they apply to."""

    def sources(self, cohort):
        return {c['source_id'] for c in Catalog('project', None, cohort).chunks if c['kind'] == 'regulation'}

    def test_each_cohort_gets_its_own_regulation(self):
        if not (ROOT / 'data' / 'project' / 'documents.json').exists():
            self.skipTest('Chưa tạo documents.json')
        self.assertTrue({'S03', 'S04', 'N02', 'N03'} <= self.sources('K37'))
        self.assertTrue({'S05', 'N01', 'N03'} <= self.sources('K38'))
        self.assertTrue({'S06', 'N04'} <= self.sources('K39'))
        self.assertFalse(self.sources('K39') & {'S03', 'S05', 'N03'})
        self.assertFalse(self.sources('K38') & {'S03', 'S04', 'S06'})
        self.assertNotIn('S04', self.sources('K35'))  # TOEIC international rule covers K36–K37 only.

    def test_ocr_text_is_labelled_and_gaps_reported(self):
        if not (ROOT / 'data' / 'project' / 'documents.json').exists():
            self.skipTest('Chưa tạo documents.json')
        catalog = Catalog('project', None, 'K37')
        ocr = [c for c in catalog.chunks if c.get('verification') == 'OCR_UNREVIEWED']
        self.assertTrue(ocr)
        self.assertIn('OCR', catalog.citation(ocr[0])['evidence_note'])
        self.assertTrue(any(g['id'].startswith('OCR-') for g in catalog.gaps))
        self.assertIn('hoc_phi', catalog.covered_topics)
        self.assertNotIn('hoc_phi', Catalog('sample', None, 'K37').covered_topics)
