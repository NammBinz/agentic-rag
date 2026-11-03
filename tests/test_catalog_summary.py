"""Regression for complete catalog counts and contextual follow-ups, without LLM calls."""
import functools
import unittest
from unittest.mock import patch
from agentic_rag.catalog import Catalog
from agentic_rag.catalog_queries import catalog_query
from agentic_rag.demo import DemoEngine
from agentic_rag.provider import Settings
from agentic_rag.server import create_app
from agentic_rag.tools import AcademicTools

QUESTION = 'ngành công nghệ thông tin cần học những môn bắt buộc nào'


class NoGeneration:
    def generate(self, *args, **kwargs):
        raise AssertionError('Catalog reports must not call the LLM')


class CatalogSummaryTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()
        engine = DemoEngine(settings=Settings(provider='gemini'), provider=NoGeneration())
        # The demo now requires a chosen cohort; these regressions are about K37.
        self.engine = engine
        self.engine.answer = functools.partial(engine.answer, cohort='K37')

    def test_mandatory_uses_exact_rule_not_group_name(self):
        r = AcademicTools(self.catalog).catalog_summary('K37', 'mandatory')
        self.assertEqual(r['count'], 45)
        self.assertEqual({g['group']: g['count'] for g in r['groups']},
                         {'Đại cương':21, 'Cơ sở khối ngành':13, 'Bắt buộc ngành':10, 'Tốt nghiệp':1})
        codes = {c['code'] for c in r['courses']}
        self.assertTrue({'EC102','CS123','IT333','IP406'} <= codes)
        self.assertFalse(codes & {'CS223','CS224','IT499','IT486','IT334'})

    def test_unique_catalog_codes_not_raw_rows(self):
        r = AcademicTools(self.catalog).catalog_summary('K37')
        self.assertEqual(r['count'],99)
        self.assertEqual(sum(c['code']=='IT334' for c in r['courses']),1)
        self.assertEqual(len({c['code'] for c in r['courses']}),99)

    def test_group_filter_preserves_choice_in_mandatory_group(self):
        r = AcademicTools(self.catalog).catalog_summary('K37', 'mandatory', 'Bắt buộc ngành')
        self.assertEqual(r['count'],10)
        self.assertEqual(r['choice_groups'][0]['codes'],['CS223','CS224'])
        self.assertIn('Chọn 1 trong 2',r['choice_groups'][0]['selection_rule'])

    def test_list_covers_every_mandatory_course_with_individual_citation(self):
        r = self.engine.answer(QUESTION)
        self.assertEqual(r['status'],'catalog_summary')
        tool=r['tool_results'][0]
        for course in tool['courses']:
            self.assertIn(course['name'],r['answer'])
            self.assertIn('[COURSE-'+course['code']+']',r['answer'])
        self.assertIn('Chọn 1 trong 2',r['answer'])
        self.assertIn('Chọn một cặp ngoại ngữ',r['answer'])
        self.assertIn('không phải số môn mỗi sinh viên phải học',r['answer'])

    def test_exact_screenshot_conversation_retains_45(self):
        history=[]
        for question in [QUESTION,'có mấy môn','là những môn gì']:
            r=self.engine.answer(question,history=history)
            self.assertEqual(r['status'],'catalog_summary')
            self.assertEqual(r['tool_results'][0]['count'],45)
            self.assertEqual(r['metrics']['tool_calls'],1)
            self.assertEqual(r['metrics']['retrieval_rounds'],0)
            self.assertEqual(r['metrics']['completion_tokens'],0)
            history.append({'question':question})
        self.assertIn('CS123',r['answer'])
        self.assertIn('IP406',r['answer'])

    def test_count_is_short_then_followup_lists_full_set(self):
        h=[{'question':QUESTION}]
        r=self.engine.answer('có mấy môn',history=h)
        self.assertNotIn('• EC102',r['answer'])
        h.append({'question':'có mấy môn'})
        r=self.engine.answer('là những môn gì',history=h)
        self.assertIn('• EC102',r['answer'])

    def test_explicit_new_filter_resets_old_context(self):
        h=[{'question':QUESTION}]
        r=self.engine.answer('ngành CNTT có tất cả bao nhiêu môn?',history=h)
        self.assertEqual(r['tool_results'][0]['count'],99)
        h.append({'question':'ngành CNTT có tất cả bao nhiêu môn?'})
        r=self.engine.answer('là những môn gì',history=h)
        self.assertEqual(r['tool_results'][0]['count'],99)

    def test_list_and_count_phrasings(self):
        for q in ['K37 có bao nhiêu học phần?', 'liệt kê tất cả môn học', 'danh sách các học phần trong chương trình CNTT']:
            with self.subTest(q=q):
                r=self.engine.answer(q)
                self.assertEqual(r['tool_results'][0]['count'],99)
        r=self.engine.answer('vậy có tổng cộng bao nhiêu môn?',history=[{'question':QUESTION}])
        self.assertEqual(r['tool_results'][0]['count'],45)

    def test_mandatory_major_and_general_groups(self):
        for q,count in [('các môn bắt buộc ngành là gì',10),('các môn đại cương bắt buộc',21),('các môn cơ sở ngành bắt buộc',13),('các môn lựa chọn ngành',23)]:
            with self.subTest(q=q):
                self.assertEqual(self.engine.answer(q)['tool_results'][0]['count'],count)

    def test_generic_count_without_history_requests_context(self):
        for q in ['có mấy môn','là những môn gì']:
            r=self.engine.answer(q)
            self.assertEqual(r['status'],'needs_input')
            self.assertEqual(r['metrics']['retrieval_rounds'],0)

    def test_intervening_subject_does_not_reuse_old_catalog_filter(self):
        for intervening in ['IT320 có mấy tín chỉ?', 'học phí bao nhiêu?']:
            r=self.engine.answer('có mấy môn',history=[{'question':QUESTION},{'question':intervening}])
            self.assertEqual(r['status'],'needs_input')

    def test_wrong_scope_in_history_not_imported(self):
        for previous in ['K38 có bao nhiêu môn bắt buộc?', 'CNTT-2025 có bao nhiêu môn?', 'ngành trí tuệ nhân tạo học những môn bắt buộc nào?']:
            r=self.engine.answer('có mấy môn',history=[{'question':previous}])
            self.assertEqual(r['status'],'needs_input')

    def test_unsupported_scope_and_missing_snapshot_never_count_as_zero(self):
        r=self.engine.answer('K38 có bao nhiêu môn bắt buộc?')
        self.assertEqual(r['status'],'out_of_scope')
        r=AcademicTools(Catalog(cohort='K38')).catalog_summary('K38')
        self.assertEqual(r['status'],'insufficient_data')

    def test_rag_mode_cannot_count_top_k_as_whole_catalog(self):
        r=self.engine.answer(QUESTION,mode='rag')
        self.assertEqual(r['tool_results'][0]['count'],45)
        self.assertEqual(r['metrics']['retrieval_rounds'],0)
        self.assertEqual(r['metrics']['completion_tokens'],0)

    def test_non_catalog_course_questions_keep_original_router(self):
        for q in ['IT320 có bao nhiêu tín chỉ?', 'Lập trình cơ sở 2 là gì?', 'IT320 yêu cầu môn nào?']:
            self.assertIsNone(catalog_query(q,self.catalog))

    def test_choices_are_not_all_required_to_be_taken(self):
        r=self.engine.answer('ngành CNTT có bao nhiêu môn tự chọn?')
        self.assertEqual(r['tool_results'][0]['count'],54)
        self.assertIn('lựa chọn hoặc nhánh thay thế',r['answer'])
        self.assertIn('không phải số môn mỗi sinh viên phải học',r['answer'])

    def test_complete_evidence_keeps_source_rows_and_scope(self):
        r=self.engine.answer(QUESTION)
        self.assertEqual(len(r['citations']),99)
        self.assertTrue(all(c['cohort']=='K37' and c['curriculum_id']=='CNTT-2024' for c in r['citations']))
        c=next(c for c in r['citations'] if c['course_code']=='CS123')
        self.assertEqual(c['workbook_row'],43)

    def test_flask_followups_work_without_google_calls(self):
        client=create_app(Settings(provider='gemini'),provider=NoGeneration()).test_client()
        h=[]
        with patch('agentic_rag.provider.urllib.request.urlopen',side_effect=AssertionError('No Google request expected')):
            for q in [QUESTION,'có mấy môn','là những môn gì']:
                response=client.post('/api/chat',json={'question':q,'history':h,'cohort':'K37'})
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json['tool_results'][0]['count'],45)
                h.append({'question':q})

    def test_disabled_tool_does_not_fall_back_to_top_k_count(self):
        r=self.engine.answer(QUESTION,enable_tools=False)
        self.assertEqual(r['status'],'insufficient_data')
        self.assertEqual(r['metrics']['tool_calls'],0)
        self.assertEqual(r['metrics']['completion_tokens'],0)

    def test_inventory_words_do_not_override_known_data_gaps(self):
        # Tuition and graduation rules now have full text; schedules and personal eligibility still do not.
        for q in ['lịch học các môn bắt buộc ngành?', 'thời khóa biểu các môn bắt buộc ngành?']:
            with self.subTest(q=q):
                r=self.engine.answer(q)
                self.assertEqual(r['status'],'insufficient_data')
                self.assertEqual(r['metrics']['completion_tokens'],0)
