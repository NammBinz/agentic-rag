import json
import math
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from agentic_rag.catalog import Catalog
from agentic_rag.engine import Engine, validate_generation
from agentic_rag.provider import Settings, ProviderError
from agentic_rag.retrieval import Retriever
from agentic_rag.server import create_server
from agentic_rag.tools import AcademicTools, validate_profile


class CatalogTests(unittest.TestCase):
    def test_project_snapshot_preserves_counts_and_duplicate(self):
        c = Catalog()
        self.assertEqual(len(c.courses), 99)
        self.assertEqual(c.manifest["counts"]["K37"]["raw_rows"], 100)
        self.assertEqual(len(c.conditions), 76)
        self.assertEqual(c.courses["IT334"]["source_row_count"], 2)
        self.assertIsNone(c.courses["CS121"]["prerequisite_raw"])

    def test_excluded_sources_cannot_be_retrieved(self):
        catalog = Catalog()
        chunks, _ = Retriever(catalog, Settings()).search("Quy chế đào tạo 2026", "K37", top_k=10)
        self.assertFalse({"S05", "S06", "S07", "S12"} & {c["source_id"] for c in chunks})
        wrong_cohort, _ = Retriever(catalog, Settings()).search("IT320", "K38")
        self.assertEqual(wrong_cohort, [])

    def test_lookup_accent_insensitive(self):
        result = AcademicTools(Catalog()).lookup("phat trien ung dung voi python", "K37")
        self.assertEqual(result["courses"][0]["code"], "IT320")
        self.assertEqual(result["citations"][0]["page"], 21)


class PrerequisiteTests(unittest.TestCase):
    def setUp(self):
        self.sample = AcademicTools(Catalog("sample"))
        self.project = AcademicTools(Catalog())

    def test_and_exact_boundary_and_failure(self):
        result = self.sample.prerequisites("PY201", "K37", {"completed": ["PY101"], "credits": 12})
        self.assertEqual(result["status"], "satisfied_in_snapshot")
        self.assertIn("12", result["citations"][0]["text"])
        for profile in ({"completed": [], "credits": 12}, {"completed": ["PY101"], "credits": 11.5}):
            self.assertEqual(self.sample.prerequisites("PY201", "K37", profile)["status"], "not_met_in_snapshot")

    def test_or_three_valued(self):
        for profile in ({"completed": ["PY101"]}, {"completed": [], "grades": {"CS101": 7}}):
            r = self.sample.prerequisites("PY202", "K37", profile)
            self.assertEqual(r["status"], "satisfied_in_snapshot")
            self.assertEqual(r["missing"], [])
        self.assertEqual(self.sample.prerequisites("PY202", "K37", {"completed": [], "grades": {"CS101": 6.9}})["status"], "not_met_in_snapshot")
        self.assertEqual(self.sample.prerequisites("PY202", "K37", {"completed": []})["status"], "insufficient_data")

    def test_average_and_grade_threshold(self):
        self.assertEqual(self.sample.prerequisites("PY203", "K37", {"grades": {"PY101": 5}, "average": 6})["status"], "satisfied_in_snapshot")
        self.assertEqual(self.sample.prerequisites("PY203", "K37", {"grades": {"PY101": 4.9}, "average": 6})["status"], "not_met_in_snapshot")

    def test_unknown_completed_list_is_not_empty_list(self):
        self.assertEqual(self.sample.prerequisites("PY201", "K37", {"completed": None, "credits": 12})["status"], "insufficient_data")
        self.assertEqual(self.sample.prerequisites("PY201", "K37", {"completed": [], "credits": 12})["status"], "not_met_in_snapshot")

    def test_blank_and_bare_code_never_mean_eligible(self):
        self.assertEqual(self.project.prerequisites("CS121", "K37", {})["status"], "insufficient_data")
        r = self.project.prerequisites("IT320", "K37", {"completed": ["CS122"], "grades": {"CS122": 10}})
        self.assertEqual(r["status"], "insufficient_data")
        self.assertTrue(r["checks"][0]["present_in_completed"])

    def test_real_explicit_thresholds_preserved(self):
        success = self.project.prerequisites("IT499", "K37", {"credits": 100, "grades": {"IP406": 4}, "average": 7})
        self.assertEqual(success["status"], "satisfied_in_snapshot")
        self.assertEqual(len(success["checks"]), 3)
        self.assertIn("không xác nhận", success["scope"])
        failure = self.project.prerequisites("IT499", "K37", {"credits": 99, "grades": {"IP406": 4}, "average": 7})
        self.assertEqual(failure["status"], "not_met_in_snapshot")

    def test_no_profile_and_unknown_code(self):
        self.assertEqual(self.sample.prerequisites("PY201", "K37")["status"], "needs_input")
        self.assertEqual(self.project.prerequisites("AD213", "K37", {})["status"], "not_found")

    def test_bad_numeric_input(self):
        for profile in ({"credits": -1}, {"grades": {"PY101": 11}}, {"average": float("nan")},
                        {"completed": "PY101"}, {"credits": True}, {"grades": {"PY101": "7"}}):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                validate_profile(profile)


class AgentTests(unittest.TestCase):
    def test_single_pass_citation_is_from_retrieved_chunk(self):
        r = Engine().answer("IT320 bao nhiêu tín chỉ?", mode="rag", cohort="K37")
        self.assertEqual(r["metrics"]["retrieval_rounds"], 1)
        self.assertEqual(r["metrics"]["tool_calls"], 0)
        self.assertEqual(r["citations"][0]["id"], "COURSE-IT320")
        self.assertIn("3", r["citations"][0]["text"])
        self.assertEqual(r["citations"][0]["content_level"], "transcribed_row")

    def test_extra_round_is_based_on_missing_evidence_and_bounded(self):
        engine = Engine("sample", Settings(top_k=1))
        with patch.object(engine.retriever, "search", wraps=engine.retriever.search) as search:
            r = engine.answer("So sánh PY201 và CS101", mode="agent", cohort="K37", enable_tools=False)
        self.assertEqual(search.call_count, 2)
        self.assertEqual(r["metrics"]["extra_retrieval_rounds"], 1)
        self.assertEqual({c["id"] for c in r["citations"]}, {"COURSE-PY201", "COURSE-CS101"})
        self.assertTrue(next(a for a in r["actions"] if a["action"] == "retrieve" and a["round"] == 2)["reason"])

    def test_disable_extra_retrieval_keeps_one_round(self):
        r = Engine("sample", Settings(top_k=1)).answer("So sánh PY201 và CS101", mode="agent", cohort="K37", enable_tools=False, enable_extra_retrieval=False)
        self.assertEqual(r["metrics"]["retrieval_rounds"], 1)
        self.assertEqual(r["status"], "insufficient_data")

    def test_agent_tool_no_llm_arithmetic(self):
        r = Engine("sample").answer("Kiểm tra tiên quyết PY201", mode="agent", cohort="K37", profile={"completed": ["PY101"], "credits": 12})
        self.assertEqual(r["status"], "satisfied_in_snapshot")
        self.assertEqual(r["metrics"]["tool_calls"], 1)
        self.assertEqual(r["tool_results"][0]["course_code"], "PY201")

    def test_course_name_and_followup_resolution(self):
        e = Engine()
        r = e.answer("Phát triển ứng dụng với Python có tiên quyết gì?", mode="agent", cohort="K37", profile={})
        self.assertEqual(r["tool_results"][0]["course_code"], "IT320")
        r = e.answer("Kiểm tra tiên quyết môn đó", mode="agent", cohort="K37", profile={}, history=[{"question": "IT320 có bao nhiêu tín chỉ?"}])
        self.assertEqual(r["tool_results"][0]["course_code"], "IT320")

    def test_information_lookup_does_not_require_profile_or_expand_unneeded_sources(self):
        e = Engine()
        for q in ("IT320 có bao nhiêu tín chỉ?", "IT320 có tiên quyết gì?"):
            r = e.answer(q, mode="agent", cohort="K37")
            self.assertIn(r["status"], ("evidence_found", "recorded_conditions"))
            self.assertLessEqual(r["metrics"]["retrieval_rounds"], 2)
            self.assertIn(r["tool_results"][0]["tool"], ("lookup_course", "lookup_conditions"))
            self.assertIn("CS122", r["answer"])

    def test_missing_cohort_and_wrong_scope_use_no_retrieval(self):
        e = Engine()
        for cohort, status in ((None, "needs_input"), ("K38", "insufficient_data"), ("K40", "out_of_scope")):
            r = e.answer("IT320", mode="agent", cohort=cohort)
            self.assertEqual(r["status"], status)
            self.assertEqual(r["metrics"]["retrieval_rounds"], 0)

    def test_missing_topics_are_not_invented(self):
        e = Engine()
        for question in ("Kỳ này còn lớp IT320 không?", "Tôi đủ điều kiện tốt nghiệp chưa?", "Lịch học IT320?"):
            for mode in ("rag", "agent"):
                self.assertEqual(e.answer(question, mode=mode, cohort="K37")["status"], "insufficient_data")

    def test_unknown_course_and_ablation(self):
        e = Engine()
        self.assertEqual(e.answer("ZZ999 có tiên quyết gì?", mode="agent", cohort="K37")["status"], "insufficient_data")
        r = e.answer("IT320 có tiên quyết gì?", mode="agent", cohort="K37", enable_tools=False)
        self.assertEqual(r["metrics"]["tool_calls"], 0)


class ProviderTests(unittest.TestCase):
    def test_generated_citations_are_verified(self):
        chunk = Catalog().chunks[0]
        good = {"status": "answered", "claims": [{"text": "Kết luận", "evidence_id": chunk["id"], "quote": chunk["text"]}], "clarification": ""}
        self.assertTrue(validate_generation(good, [chunk]))
        for field, value in (("evidence_id", "FAKE-ID"), ("quote", "Nội dung bịa"), ("quote", "")):
            bad = json.loads(json.dumps(good)); bad["claims"][0][field] = value
            self.assertFalse(validate_generation(bad, [chunk]))

    def test_invalid_citation_blocks_output_and_records_tokens(self):
        class FakeProvider:
            def generate(self, *args, **kwargs):
                return {"status": "answered", "claims": [{"text": "Học phí 1 triệu", "evidence_id": "FAKE", "quote": "x"}]}, {"prompt_tokens": 10, "completion_tokens": 4}
        r = Engine(settings=Settings(provider="openai"), provider=FakeProvider()).answer("IT320", cohort="K37")
        self.assertEqual(r["status"], "insufficient_data")
        self.assertEqual(r["citations"], [])
        self.assertEqual(r["metrics"]["prompt_tokens"], 10)
        self.assertNotIn("1 triệu", r["answer"])

    def test_hybrid_cache_and_query_usage(self):
        class FakeEmbeddings:
            def __init__(self): self.calls = []
            def embeddings(self, texts):
                self.calls.append(len(texts))
                return [[1.0, float("PY201" in t)] for t in texts], {"total_tokens": len(texts)*2}
        catalog = Catalog("sample"); settings = Settings(provider="openai", retriever="hybrid")
        with tempfile.TemporaryDirectory() as folder:
            fake = FakeEmbeddings(); retriever = Retriever(catalog, settings, fake, folder)
            chunks, usage = retriever.search("PY201", "K37")
            self.assertEqual(chunks[0]["id"], "COURSE-PY201")
            self.assertGreater(usage["index_embedding_tokens"], 0)
            _, second = retriever.search("PY202", "K37")
            self.assertEqual(second["index_embedding_tokens"], 0)
            new = Retriever(catalog, settings, fake, folder); new.search("PY201", "K37")
            self.assertEqual(fake.calls.count(len(catalog.chunks)), 1)


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(port=0, settings=Settings(), demo_only=False)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start(); cls.base = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=2)

    def request(self, path, body=None, headers=None):
        h = {"Content-Type": "application/json"}; h.update(headers or {})
        req = urllib.request.Request(self.base + path, data=None if body is None else json.dumps(body).encode(), headers=h)
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as r:
            return r.code, r.read()

    def test_chat_and_direct_tools_end_to_end(self):
        status, body = self.request("/api/chat", {"question": "Kiểm tra tiên quyết PY201", "mode": "agent", "cohort": "K37", "dataset": "sample", "profile": {"completed": ["PY101"], "credits": 12}})
        self.assertEqual(status, 200); self.assertEqual(json.loads(body)["status"], "satisfied_in_snapshot")
        status, body = self.request("/api/courses?q=IT320&cohort=K37")
        self.assertEqual(json.loads(body)["courses"][0]["credits"], 3)
        status, body = self.request("/api/prerequisites", {"dataset": "project", "course_code": "IT499", "cohort": "K37", "profile": {"credits": 90}})
        self.assertEqual(status, 200); self.assertEqual(json.loads(body)["status"], "not_met_in_snapshot")

    def test_sources_and_static_security(self):
        status, body = self.request("/api/chunks/COURSE-IT320?cohort=K37")
        self.assertEqual(status, 200); self.assertEqual(json.loads(body)["page"], 21)
        self.assertEqual(self.request("/")[0], 200)
        for path in ("/../.env", "/%2e%2e/.env", "/api/unknown"):
            self.assertEqual(self.request(path)[0], 404)

    def test_bad_inputs_and_cross_origin_blocked(self):
        for body in ({"question": "", "cohort": "K37"}, {"question": "IT320", "dataset": "bad"},
                     {"question": "IT320", "history": [5]}, {"question": "IT320", "cohort": ["K37"]},
                     {"question": "IT320", "cohort": "K37", "profile": {"average": math.nan}}):
            self.assertEqual(self.request("/api/chat", body)[0], 400)
        status, _ = self.request("/api/chat", {"question": "IT320"}, {"Origin": "https://elsewhere.example"})
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
