"""Gemini transport, isolation, and grounded Flask integration without network calls."""
import io
import json
import os
import unittest
import urllib.error
from unittest.mock import patch

from agentic_rag.catalog import Catalog
from agentic_rag.provider import Settings, GeminiProvider, OpenAIProvider, ProviderError, create_provider
from agentic_rag.server import create_app


class GeminiTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"GEMINI_API_KEY": "test-google-key", "OPENAI_API_KEY": "test-openai-key"}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.chunk = next(c for c in Catalog().chunks if c['id'] == 'COURSE-IT320')
        self.output = {'status': 'answered', 'claims': [{'text': 'IT320: 3 tín chỉ.', 'evidence_id': self.chunk['id'], 'quote': self.chunk['text']}], 'clarification': ''}

    def response(self, content=None):
        return io.BytesIO(json.dumps({'choices': [{'message': {'content': json.dumps(self.output, ensure_ascii=False) if content is None else content}}], 'usage': {'prompt_tokens': 30, 'completion_tokens': 12}}).encode())

    def test_provider_defaults_and_explicit_model(self):
        self.assertEqual(Settings(provider='gemini').model, 'gemini-3.8-flash')
        self.assertEqual(Settings().model, 'gpt-4.1-mini')
        self.assertEqual(Settings(provider='gemini', model='custom').model, 'custom')
        with self.assertRaises(ValueError):
            Settings(provider='gemini', retriever='hybrid')

    def test_env_selects_gemini_model_without_openai_model(self):
        with patch.dict(os.environ, {'RAG_PROVIDER': 'gemini', 'OPENAI_MODEL': 'wrong-provider-model'}):
            self.assertEqual(Settings.from_env().model, 'gemini-3.8-flash')
            with patch.dict(os.environ, {'GEMINI_MODEL': 'custom-gemini'}):
                self.assertEqual(Settings.from_env().model, 'custom-gemini')

    def test_factory_selects_correct_provider_and_credentials(self):
        self.assertIsNone(create_provider(Settings()))
        self.assertIsInstance(create_provider(Settings(provider='gemini')), GeminiProvider)
        self.assertEqual(create_provider(Settings(provider='gemini')).key, 'test-google-key')
        self.assertEqual(create_provider(Settings(provider='openai')).key, 'test-openai-key')

    def test_missing_google_key_does_not_use_openai_key(self):
        os.environ.pop('GEMINI_API_KEY')
        with self.assertRaisesRegex(ProviderError, 'GEMINI_API_KEY'):
            create_provider(Settings(provider='gemini'))

    def test_google_transport_schema_and_selected_evidence(self):
        with patch('agentic_rag.provider.urllib.request.urlopen', return_value=self.response()) as send:
            output, usage = GeminiProvider(Settings(provider='gemini')).generate('IT320?', [self.chunk], 'K37')
        req = send.call_args.args[0]
        self.assertEqual(req.full_url, 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions')
        self.assertEqual(req.get_header('Authorization'), 'Bearer test-google-key')
        payload = json.loads(req.data)
        self.assertEqual(payload['model'], 'gemini-3.8-flash')
        self.assertEqual(payload['max_tokens'], 4096)
        self.assertNotIn('max_completion_tokens', payload)
        self.assertEqual(payload['response_format']['type'], 'json_schema')
        evidence = json.loads(payload['messages'][1]['content'])
        self.assertEqual(evidence['cohort'], 'K37')
        self.assertEqual([c['id'] for c in evidence['evidence']], ['COURSE-IT320'])
        self.assertNotIn('test-google-key', req.data.decode())
        self.assertEqual(output, self.output)
        self.assertEqual(usage['completion_tokens'], 12)

    def test_openai_transport_stays_on_openai(self):
        with patch('agentic_rag.provider.urllib.request.urlopen', return_value=self.response()) as send:
            OpenAIProvider(Settings(provider='openai')).generate('IT320?', [self.chunk], 'K37')
        req = send.call_args.args[0]
        self.assertEqual(req.full_url, 'https://api.openai.com/v1/chat/completions')
        self.assertEqual(req.get_header('Authorization'), 'Bearer test-openai-key')
        self.assertEqual(json.loads(req.data)['max_completion_tokens'], 1600)

    def test_gemini_embedding_is_explicitly_unavailable(self):
        with patch('agentic_rag.provider.urllib.request.urlopen') as send:
            with self.assertRaises(ProviderError):
                GeminiProvider(Settings(provider='gemini')).embeddings(['test'])
            send.assert_not_called()

    def test_invalid_json_and_malformed_response_fail_clearly(self):
        for response in [self.response('not json'), io.BytesIO(b'{"choices": []}')]:
            with self.subTest(), patch('agentic_rag.provider.urllib.request.urlopen', return_value=response):
                with self.assertRaises(ProviderError):
                    GeminiProvider(Settings(provider='gemini')).generate('IT320?', [self.chunk], 'K37')

    def test_gemini_flask_grounded_output_and_usage(self):
        app = create_app(Settings(provider='gemini'))
        with patch('agentic_rag.provider.urllib.request.urlopen', return_value=self.response()) as send:
            response = app.test_client().post('/api/chat', json={'question': 'IT320 tên gì, mấy tín chỉ?', 'mode': 'agent'})
        self.assertEqual(response.status_code, 200)
        body = response.json
        self.assertEqual(body['status'], 'answered')
        self.assertEqual(body['config']['provider'], 'gemini')
        self.assertEqual(body['metrics']['completion_tokens'], 12)
        self.assertTrue(any(c['id'] == 'COURSE-IT320' for c in body['citations']))
        self.assertTrue(body['tool_results'])
        self.assertEqual([a for a in body['actions'] if a['action'] == 'generate'], [{'action': 'generate', 'provider': 'gemini'}])
        self.assertEqual(send.call_count, 1)
        health = app.test_client().get('/api/health').json
        self.assertEqual(health['provider'], 'gemini')
        self.assertEqual(health['model'], 'gemini-3.8-flash')
        self.assertTrue(health['demo_only'])
        self.assertNotIn('test-google-key', json.dumps(body) + json.dumps(health))

    def test_invalid_claim_is_blocked_after_gemini_generation(self):
        self.output['claims'][0]['evidence_id'] = 'FAKE-ID'
        app = create_app(Settings(provider='gemini'))
        with patch('agentic_rag.provider.urllib.request.urlopen', return_value=self.response()):
            body = app.test_client().post('/api/chat', json={'question': 'IT320'}).json
        self.assertEqual(body['status'], 'insufficient_data')
        self.assertEqual(body['citations'], [])
        self.assertEqual(body['metrics']['completion_tokens'], 12)

    def test_scope_blocked_before_google_request(self):
        client = create_app(Settings(provider='gemini')).test_client()
        with patch('agentic_rag.provider.urllib.request.urlopen') as send:
            for question in ['K38 tra IT320', 'IT320 phiên bản CNTT-2025']:
                body = client.post('/api/chat', json={'question': question}).json
                self.assertEqual(body['status'], 'out_of_scope')
                self.assertEqual(body['metrics']['retrieval_rounds'], 0)
            for path in ['/api/catalog?dataset=sample', '/api/catalog?cohort=K38']:
                self.assertEqual(client.get(path).status_code, 400)
            send.assert_not_called()

    def test_google_error_returns_502_without_secret_or_offline_fallback(self):
        client = create_app(Settings(provider='gemini')).test_client()
        error = urllib.error.HTTPError('https://generativelanguage.googleapis.com/', 429, 'test-google-key', {}, io.BytesIO(b'test-google-key'))
        with patch('agentic_rag.provider.urllib.request.urlopen', side_effect=error),                 patch('agentic_rag.provider.time.sleep'):
            response = client.post('/api/chat', json={'question': 'IT320'})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json['code'], 'provider_error')
        self.assertIn('429', response.json['error'])
        self.assertNotIn('test-google-key', response.get_data(as_text=True))


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"GEMINI_API_KEY": "test-google-key"}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.sleep = patch('agentic_rag.provider.time.sleep')
        self.slept = self.sleep.start()
        self.addCleanup(self.sleep.stop)
        self.chunk = next(c for c in Catalog().chunks if c['id'] == 'COURSE-IT320')
        self.ok = {'status': 'answered', 'claims': [{'text': 'IT320', 'evidence_id': 'COURSE-IT320', 'quote': self.chunk['text']}], 'clarification': ''}

    def body(self):
        return io.BytesIO(json.dumps({'choices': [{'message': {'content': json.dumps(self.ok, ensure_ascii=False)}}],
                                      'usage': {'prompt_tokens': 5, 'completion_tokens': 2}}).encode())

    @staticmethod
    def http(code, headers=None):
        return urllib.error.HTTPError('https://example.invalid/', code, 'error', headers or {}, io.BytesIO(b''))

    def test_transient_503_then_success_records_retry(self):
        with patch('agentic_rag.provider.urllib.request.urlopen', side_effect=[self.http(503), self.body()]) as send:
            output, usage = GeminiProvider(Settings(provider='gemini')).generate('IT320?', [self.chunk], 'K37')
        self.assertEqual(send.call_count, 2)
        self.assertEqual(output['status'], 'answered')
        self.assertEqual(usage['api_retries'], 1)
        self.assertEqual(self.slept.call_count, 1)

    def test_network_timeout_is_retried(self):
        with patch('agentic_rag.provider.urllib.request.urlopen', side_effect=[TimeoutError(), self.body()]):
            _, usage = GeminiProvider(Settings(provider='gemini')).generate('IT320?', [self.chunk], 'K37')
        self.assertEqual(usage['api_retries'], 1)

    def test_retries_are_bounded(self):
        with patch('agentic_rag.provider.urllib.request.urlopen', side_effect=self.http(503)) as send:
            with self.assertRaisesRegex(ProviderError, '503.*3 lần'):
                GeminiProvider(Settings(provider='gemini', max_retries=2)).generate('IT320?', [self.chunk], 'K37')
        self.assertEqual(send.call_count, 3)

    def test_auth_errors_are_not_retried(self):
        for code in (400, 401, 403, 404):
            with self.subTest(code=code), patch('agentic_rag.provider.urllib.request.urlopen', side_effect=self.http(code)) as send:
                with self.assertRaises(ProviderError):
                    GeminiProvider(Settings(provider='gemini')).generate('IT320?', [self.chunk], 'K37')
                self.assertEqual(send.call_count, 1)
        self.slept.assert_not_called()

    def test_retry_after_header_is_capped(self):
        with patch('agentic_rag.provider.urllib.request.urlopen', side_effect=[self.http(429, {'Retry-After': '999'}), self.body()]):
            GeminiProvider(Settings(provider='gemini')).generate('IT320?', [self.chunk], 'K37')
        self.assertLessEqual(self.slept.call_args.args[0], 20.5)

    def test_zero_retries_and_env_settings(self):
        with patch('agentic_rag.provider.urllib.request.urlopen', side_effect=self.http(503)) as send:
            with self.assertRaises(ProviderError):
                GeminiProvider(Settings(provider='gemini', max_retries=0)).generate('IT320?', [self.chunk], 'K37')
        self.assertEqual(send.call_count, 1)
        with patch.dict(os.environ, {'RAG_MAX_RETRIES': '4', 'RAG_TIMEOUT_SECONDS': '10'}):
            settings = Settings.from_env()
        self.assertEqual((settings.max_retries, settings.timeout_seconds), (4, 10.0))
        with self.assertRaises(ValueError):
            Settings(max_retries=9)

    def test_engine_metrics_count_retries(self):
        app = create_app(Settings(provider='gemini'))
        with patch('agentic_rag.provider.urllib.request.urlopen', side_effect=[self.http(503), self.body()]):
            body = app.test_client().post('/api/chat', json={'question': 'IT320 tên gì?', 'mode': 'rag'}).json
        self.assertEqual(body['metrics']['api_retries'], 1)
