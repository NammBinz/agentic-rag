"""LLM planner: the model picks tools, Python keeps scope, budgets and grounded output."""
import io
import json
import os
import unittest
from unittest.mock import patch

from agentic_rag import llm_agent
from agentic_rag.engine import Engine
from agentic_rag.provider import GeminiProvider, Settings


def call(name, args, call_id=None):
    arguments = args if isinstance(args, str) else json.dumps(args)
    return {"id": call_id or name, "type": "function", "function": {"name": name, "arguments": arguments}}


class ScriptedProvider:
    """Plays back planning turns; generate() quotes the first matching evidence verbatim."""
    def __init__(self, turns, cite=None):
        self.turns, self.cite = list(turns), cite
        self.chat_calls, self.generate_calls = [], []

    def chat(self, messages, tools):
        self.chat_calls.append([dict(m) for m in messages])
        calls = self.turns.pop(0) if self.turns else []
        message = {"role": "assistant", "content": None if calls else "DONE"}
        if calls:
            message["tool_calls"] = calls
        return message, {"prompt_tokens": 10, "completion_tokens": 2}

    def generate(self, question, chunks, cohort, mode="rag"):
        self.generate_calls.append([c["id"] for c in chunks])
        chunk = next((c for c in chunks if c["id"] == self.cite), chunks[0])
        return ({"status": "answered", "clarification": "",
                 "claims": [{"text": "Theo nguồn.", "evidence_id": chunk["id"], "quote": chunk["text"][:40]}]},
                {"prompt_tokens": 20, "completion_tokens": 5})


class LLMPlannerTests(unittest.TestCase):
    def engine(self, provider):
        return Engine("project", Settings(provider="gemini"), provider=provider, cohort="K37")

    def ask(self, provider, question, **options):
        return self.engine(provider).answer(question, mode="agent", cohort="K37", planner="llm", **options)

    def test_model_chosen_lookup_is_grounded(self):
        provider = ScriptedProvider([[call("lookup_course", {"query": "IT320"})]], cite="COURSE-IT320")
        result = self.ask(provider, "Môn Python bên CNTT mấy tín chỉ?")
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["config"]["planner"], "llm")
        self.assertEqual([c["id"] for c in result["citations"]], ["COURSE-IT320"])
        self.assertEqual((result["metrics"]["planner_calls"], result["metrics"]["tool_calls"]), (2, 1))
        self.assertTrue(any(a["action"] == "lookup_course" and a["planner"] == "llm" for a in result["actions"]))
        self.assertEqual(result["metrics"]["prompt_tokens"], 10 * 2 + 20)

    def test_catalog_count_is_computed_not_generated(self):
        provider = ScriptedProvider([[call("catalog_summary", {"subset": "mandatory"})]])
        result = self.ask(provider, "Chương trình có bao nhiêu môn bắt buộc vậy?")
        self.assertEqual(result["status"], "catalog_summary")
        self.assertIn("45 mã học phần", result["answer"])
        self.assertEqual(provider.generate_calls, [])

    def test_prerequisite_status_comes_from_tool(self):
        profile = {"credits": 100, "grades": {"IP406": 4}, "average": 7}
        provider = ScriptedProvider([[call("check_prerequisites", {"course_code": "IT499"})]], cite="TOOL-1")
        result = self.ask(provider, "Tôi có làm được khóa luận IT499 không?", profile=profile)
        self.assertEqual(result["status"], "satisfied_in_snapshot")
        self.assertIn("TOOL-1", provider.generate_calls[0])
        self.assertIn("không xác nhận quyền đăng ký", result["answer"])

    def test_budgets_stop_a_looping_model(self):
        search = [call("search_documents", {"query": "quy chế"}, f"s{i}") for i in range(3)]
        provider = ScriptedProvider([search, search, search, search, search])
        result = self.ask(provider, "Quy chế nói gì về học vượt?")
        metrics = result["metrics"]
        self.assertEqual(metrics["planner_calls"], llm_agent.MAX_TURNS)
        self.assertEqual(metrics["retrieval_rounds"], llm_agent.MAX_SEARCHES)
        self.assertEqual(metrics["tool_calls"], llm_agent.MAX_TOOL_CALLS)
        self.assertIn("Chạm giới hạn", next(a for a in result["actions"] if a["action"] == "stop")["reason"])

    def test_unknown_tool_and_bad_arguments_are_rejected(self):
        provider = ScriptedProvider([[call("delete_records", {}), call("lookup_course", "{not json"),
                                      call("get_conditions", {"course_code": "IT320", "depth": 9})]])
        result = self.ask(provider, "IT320 cần gì?")
        rejected = [a for a in result["actions"] if a["action"] == "rejected_tool_call"]
        self.assertEqual(len(rejected), 3)
        tool_messages = [m for m in provider.chat_calls[1] if m["role"] == "tool"]
        self.assertTrue(all(json.loads(m["content"])["status"] == "error" for m in tool_messages))

    def test_cohort_and_profile_never_come_from_the_model(self):
        provider = ScriptedProvider([[call("lookup_course", {"query": "IT320", "cohort": "K38"})]], cite="COURSE-IT320")
        result = self.ask(provider, "IT320?")
        self.assertTrue(all(c["cohort"] == "K37" for c in result["citations"]))
        names = {t["function"]["name"] for t in llm_agent.tool_schemas({"Đại cương"})}
        for tool in llm_agent.tool_schemas({"Đại cương"}):
            self.assertNotIn("cohort", tool["function"]["parameters"]["properties"])
            self.assertNotIn("profile", tool["function"]["parameters"]["properties"])
        self.assertEqual(names, {"search_documents", "lookup_course", "get_conditions", "check_prerequisites", "catalog_summary"})

    def test_scope_and_missing_data_gates_run_before_planning(self):
        provider = ScriptedProvider([])
        for question, status in [("Ngành Ngôn ngữ Anh có bao nhiêu môn?", "out_of_scope"),
                                 ("Lịch học tuần sau thế nào?", "insufficient_data")]:
            with self.subTest(question=question):
                self.assertEqual(self.ask(provider, question)["status"], status)
        self.assertEqual(provider.chat_calls, [])

    def test_followup_history_reaches_the_planner(self):
        provider = ScriptedProvider([[call("get_conditions", {"course_code": "IT320", "depth": 1})]], cite="COURSE-IT320")
        self.ask(provider, "Môn đó yêu cầu gì?", history=[{"question": "IT320 mấy tín chỉ?"}])
        self.assertIn("IT320 mấy tín chỉ?", provider.chat_calls[0][1]["content"])

    def test_requires_provider_and_valid_planner(self):
        offline = Engine("project", Settings(), cohort="K37")
        self.assertEqual(offline.answer("IT320?", mode="agent", cohort="K37", planner="llm")["status"], "unavailable")
        with self.assertRaises(ValueError):
            offline.answer("IT320?", mode="agent", cohort="K37", planner="magic")
        self.assertIsNone(offline.answer("IT320?", mode="rag", cohort="K37")["config"]["planner"])


class ChatTransportTests(unittest.TestCase):
    def test_tools_sent_and_raw_message_echoed(self):
        message = {"role": "assistant", "content": None, "tool_calls": [dict(call("lookup_course", {"query": "IT320"}),
                   extra_content={"google": {"thought_signature": "sig"}})]}
        body = io.BytesIO(json.dumps({"choices": [{"message": message}], "usage": {"prompt_tokens": 3}}).encode())
        with patch.dict(os.environ, {"GEMINI_API_KEY": "k"}, clear=True), \
                patch("agentic_rag.provider.urllib.request.urlopen", return_value=body) as send:
            reply, usage = GeminiProvider(Settings(provider="gemini")).chat([{"role": "user", "content": "x"}],
                                                                           llm_agent.tool_schemas({"Đại cương"}))
        payload = json.loads(send.call_args.args[0].data)
        self.assertEqual(payload["tool_choice"], "auto")
        self.assertEqual(len(payload["tools"]), 5)
        self.assertEqual(reply["tool_calls"][0]["extra_content"]["google"]["thought_signature"], "sig")
        self.assertNotIn("content", reply)
        self.assertEqual(usage["api_retries"], 0)
