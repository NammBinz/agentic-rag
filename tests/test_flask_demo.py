"""Deployed Flask scope and LLM wiring, using mock generation only."""
import json
import unittest
from agentic_rag.catalog import Catalog
from agentic_rag.server import create_app
from agentic_rag.provider import Settings

class FlaskDemoTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(Settings())
        self.client = self.app.test_client()
    def test_fixed_scope_and_snapshot(self):
        self.assertEqual(self.client.get('/api/health').json['framework'], 'Flask')
        r = self.client.get('/api/catalog').json
        self.assertEqual(r['context']['curriculum_id'],'CNTT-2024')
        self.assertEqual(len(r['courses']),99)
        self.assertEqual(r['manifest']['source_blank_count'],31)
        for path in ('/api/catalog?cohort=K38','/api/catalog?dataset=sample',
                     '/api/conditions?q=IT320&cohort=K38','/api/courses?q=IT320&curriculum_id=wrong'):
            self.assertEqual(self.client.get(path).status_code,400)
    def test_all_cohort_notations_rejected_before_retrieval(self):
        for question in ('K38 dùng bảng K37 được không?', 'Học phần cho K40?', 'khóa 38 tra IT320', 'ngành Trí tuệ nhân tạo học gì?', 'IT320 phiên bản CNTT-2025'):
            r = self.client.post('/api/chat',json={'question':question}).json
            self.assertEqual(r['status'],'out_of_scope')
            self.assertEqual(r['metrics']['retrieval_rounds'],0)
        r = self.client.post('/api/chat',json={'question':'IT320','curriculum_id':'wrong'})
        self.assertEqual(r.status_code,400)
    def test_two_tools_and_related_source(self):
        r = self.client.get('/api/conditions?q=IT320&depth=2').json
        self.assertEqual([n['course_code'] for n in r['nodes']],['IT320','CS122','CS121'])
        r = self.client.post('/api/chat',json={'question':'IT320 yêu cầu môn nào? Môn đó yêu cầu gì?','mode':'agent'}).json
        self.assertEqual(r['tool_results'][0]['tool'],'lookup_conditions')
        self.assertEqual(r['metrics']['retrieval_rounds'],2)
        self.assertIn('CS121',r['answer'])
        self.assertLess(len(r['citations']),99)
    def test_flask_input_and_origin_validation(self):
        for body in ({'question':'IT320','profile':{'credits':True}}, {'question':'IT320','history':[5]}, {'question':'IT320','dataset':'sample'}):
            self.assertEqual(self.client.post('/api/chat',json=body).status_code,400)
        self.assertEqual(self.client.post('/api/chat',json={'question':'IT320'},headers={'Origin':'https://other.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/chat',data='{}',content_type='text/plain').status_code,400)
    def test_llm_receives_only_selected_evidence_after_tool(self):
        class FakeProvider:
            calls=[]
            def generate(self, question, chunks, cohort, **options):
                self.calls.append((question,chunks,cohort))
                first=chunks[0]
                return {'status':'answered','claims':[{'text':first['text'],'evidence_id':first['id'],'quote':first['text']}], 'clarification':''}, {'prompt_tokens':10,'completion_tokens':5}
        fake=FakeProvider()
        app=create_app(Settings(provider='openai'),provider=fake)
        r=app.test_client().post('/api/chat',json={'question':'IT320 yêu cầu môn nào? Môn đó yêu cầu gì?'}).json
        self.assertEqual(len(fake.calls),1)
        self.assertTrue(0 < len(fake.calls[0][1]) < 99)
        self.assertEqual(fake.calls[0][2],'K37')
        self.assertEqual(r['metrics']['prompt_tokens'],10)
        self.assertEqual(r['tool_results'][0]['tool'],'lookup_conditions')
    def test_source_labels_and_original_metadata_retained(self):
        c=Catalog()
        self.assertEqual(len(c.sources),12)
        self.assertEqual(c.manifest['workbook_sha256'],'0a8d80f0d04634f1335fd80aa29b6a3756a914b10cb5a195b681e0ee19a5db5c')
        r=self.client.get('/api/chunks/COURSE-IT320').json
        self.assertEqual(r['page'],21)
        self.assertEqual(r['workbook_sheet'],'Hoc phan')
        self.assertIn('chưa nhập toàn văn',r['evidence_note'])
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.get('/app.js').status_code,200)
        self.assertEqual(self.client.get('/.env').status_code,404)
