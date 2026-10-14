"""One-pass baseline; the bounded Agent is added as a separate orchestration path."""
import json
import os
import time
from .catalog import Catalog, course_codes, SUPPORTED_COHORTS
import re
from .provider import OpenAIProvider, Settings
from .retrieval import Retriever
from .planner import plan, missing_evidence
from .tools import AcademicTools, validate_profile


def validate_generation(output, chunks):
    """Validate citation existence and verbatim excerpts, not semantic entailment."""
    by_id = {c["id"]: c for c in chunks}
    if not isinstance(output, dict) or output.get("status") not in ("answered", "insufficient_data"):
        return False
    claims = output.get("claims")
    if not isinstance(claims, list) or len(claims) > 20:
        return False
    for claim in claims:
        if not isinstance(claim, dict) or not all(isinstance(claim.get(k), str) for k in ("text", "evidence_id", "quote")):
            return False
        chunk = by_id.get(claim["evidence_id"])
        if not chunk or not claim["quote"].strip() or claim["quote"] not in chunk["text"]:
            return False
        if chunk["kind"] == "gap" and output["status"] == "answered":
            return False
    return bool(claims) or output["status"] == "insufficient_data"


class Engine:
    def __init__(self, dataset="project", settings=None, provider=None, cache_dir=None, cohort="K37", data_root=None):
        self.catalog = Catalog(dataset, data_root, cohort)
        self.settings = settings or Settings()
        self.provider = provider or (OpenAIProvider(self.settings) if self.settings.provider == "openai" else None)
        self.retriever = Retriever(self.catalog, self.settings, self.provider, cache_dir)
        self.tools = AcademicTools(self.catalog)
        self.cache_dir = cache_dir
        self.scoped_engines = {}

    def for_cohort(self, cohort):
        if cohort == self.catalog.cohort:
            return self
        if cohort not in self.scoped_engines:
            self.scoped_engines[cohort] = Engine(self.catalog.dataset, self.settings, self.provider,
                                               self.cache_dir, cohort, self.catalog.data_root)
        return self.scoped_engines[cohort]

    def answer(self, question, mode="rag", cohort=None, profile=None, **options):
        if cohort is not None and not isinstance(cohort, str):
            raise ValueError("cohort phải là chuỗi hoặc null")
        if cohort != self.catalog.cohort:
            return self.for_cohort(cohort).answer(question, mode, cohort, profile, **options)
        started = time.perf_counter()
        if not isinstance(question, str) or not question.strip() or len(question) > 3000:
            raise ValueError("Câu hỏi phải có 1–3000 ký tự")
        if mode not in ("rag", "agent", "llm"):
            raise ValueError("mode phải là rag, agent hoặc llm")
        profile = validate_profile(profile)
        if set(options) - {"intent", "target_course", "history", "enable_tools", "enable_extra_retrieval"}:
            raise ValueError("Tùy chọn không được hỗ trợ")
        for flag in ("enable_tools", "enable_extra_retrieval"):
            if flag in options and not isinstance(options[flag], bool):
                raise ValueError(flag + " phải là boolean")
        metrics = {"retrieval_rounds": 0, "extra_retrieval_rounds": 0, "tool_calls": 0,
                   "prompt_tokens": 0, "completion_tokens": 0, "embedding_tokens": 0,
                   "index_embedding_tokens": 0, "estimated_cost_usd": None}
        result = {"question": question, "mode": mode, "dataset": self.catalog.dataset,
                  "cohort": cohort, "context": self.catalog.context,
                  "citations": [], "actions": [], "tool_results": [], "metrics": metrics,
                  "config": {"provider": self.settings.provider, "retriever": self.settings.retriever,
                             "model": self.settings.model if self.provider else None, "top_k": self.settings.top_k,
                             "catalog_fingerprint": self.catalog.fingerprint, "max_extra_retrievals": 1},
                  "notice": ("DỮ LIỆU GIẢ LẬP — chỉ dùng kiểm thử." if self.catalog.dataset == "sample" else
                             self.catalog.context["message"] + " Chưa nhập toàn văn quy chế.")}

        def finish(status, answer, chunks=()):
            result.update(status=status, answer=answer,
                          citations=[self.catalog.citation(c) for c in chunks])
            metrics["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
            metrics["cost_note"] = "Không ước tính nếu chưa cấu hình đơn giá; token API là số thực trả về."
            if not self.provider:
                metrics["estimated_cost_usd"] = 0.0
            else:
                prices = [os.getenv(k) for k in ("INPUT_USD_PER_MILLION", "OUTPUT_USD_PER_MILLION", "EMBEDDING_USD_PER_MILLION")]
                if all(p is not None and p != "" for p in prices):
                    try:
                        metrics["estimated_cost_usd"] = round(sum(float(p) * n / 1_000_000 for p, n in zip(prices,
                            (metrics["prompt_tokens"], metrics["completion_tokens"], metrics["embedding_tokens"] + metrics["index_embedding_tokens"]))), 8)
                    except ValueError:
                        pass
            return result

        if not cohort:
            return finish("needs_input", "Bạn thuộc khóa nào? Chọn K35–K39, ngành Công nghệ thông tin.")
        if cohort not in SUPPORTED_COHORTS:
            return finish("out_of_scope", self.catalog.context["message"])
        mentioned = set(re.findall(r"\bK(?:35|36|37|38|39)\b", question.upper()))
        if mentioned and mentioned != {cohort}:
            return finish("needs_input", f"Bạn đang chọn {cohort} nhưng câu hỏi nhắc khóa khác. Hãy chọn đúng khóa; so sánh nhiều khóa cần hỏi riêng từng khóa.")
        if mode == "llm":
            if not self.provider:
                return finish("unavailable", "Đối chứng LLM không RAG cần RAG_PROVIDER=openai và khóa API ở máy chủ.")
            output, usage = self.provider.generate(question, [], cohort, mode="llm")
            self._usage(metrics, usage)
            text = "\n".join(c.get("text", "") for c in output.get("claims", [])) + "\n" + output.get("clarification", "")
            result["notice"] += " Đối chứng không truy xuất; câu trả lời chưa được đối chiếu nguồn."
            return finish(output.get("status", "insufficient_data"), text.strip())

        route = plan(question, self.catalog, intent=options.get("intent"),
                     target_course=options.get("target_course"), history=options.get("history"))
        if self.catalog.context['status'] != 'verified_snapshot' and (
                route['intent'] in ('lookup', 'prerequisites') or course_codes(question)):
            return finish("insufficient_data", self.catalog.context['message'])
        if mode == "agent":
            result["actions"].append({"action": "route", **route})
            if route["needs_target"] or len(route["targets"]) > 4:
                return finish("needs_input", "Hãy chọn 1–4 mã học phần cần tra/kiểm tra.")
            question = route["resolved_question"]
        chunks, usage = self.retriever.search(question, cohort,
                                              source_ids=route["source_ids"] if mode == "agent" else None)
        self._usage(metrics, usage)
        metrics["retrieval_rounds"] = 1
        result["actions"].append({"action": "retrieve", "round": 1, "query": question,
                                  "chunk_ids": [c["id"] for c in chunks]})
        if mode == "agent":
            if options.get("enable_tools", True) and route["intent"] in ("lookup", "prerequisites"):
                for target in route["targets"]:
                    tool = (self.tools.prerequisites(target, cohort, profile) if route["intent"] == "prerequisites"
                            else self.tools.lookup(target, cohort))
                    metrics["tool_calls"] += 1
                    result["tool_results"].append(tool)
                    result["actions"].append({"action": tool["tool"], "target": target, "status": tool["status"]})
                    present = {c["id"] for c in chunks}
                    chunks += [c for c in tool["citations"] if c["id"] not in present]
            missing = missing_evidence(question, route["targets"], chunks, self.catalog,
                                       include_dependencies=route["intent"] == "prerequisites")
            result["actions"].append({"action": "check_evidence", "missing_course_records": missing,
                                      "missing_topic": route["missing_topic"]})
            if missing and options.get("enable_extra_retrieval", True):
                followup = " ".join(missing)
                extra, usage = self.retriever.search(followup, cohort, kinds=["course"])
                self._usage(metrics, usage)
                metrics.update(retrieval_rounds=2, extra_retrieval_rounds=1)
                result["actions"].append({"action": "retrieve", "round": 2, "query": followup,
                                          "reason": "Thiếu bản ghi môn được hỏi hoặc môn tiên quyết trực tiếp.",
                                          "chunk_ids": [c["id"] for c in extra]})
                present = {c["id"] for c in chunks}
                chunks += [c for c in extra if c["id"] not in present]
            result["actions"].append({"action": "stop", "reason": "Đã kiểm tra công cụ/chứng cứ; giới hạn tối đa 2 lượt truy xuất."})
            if route["missing_topic"]:
                gaps = [c for c in chunks if c["kind"] in ("gap", "scope")]
                return finish("insufficient_data", route["missing_topic"] + " Cần bổ sung văn bản đúng khóa và còn hiệu lực.", gaps)
            if route["intent"] == "prerequisites" and result["tool_results"]:
                statuses = [t["status"] for t in result["tool_results"]]
                status = statuses[0] if len(set(statuses)) == 1 else "mixed_results"
                if status == "not_found":
                    status = "insufficient_data"
                parts = []
                citations = []
                seen = set()
                for tool in result["tool_results"]:
                    part = f'{tool["course_code"]}: {tool["message"]}'
                    for check in tool["checks"]:
                        part += f'\n• {check.get("quote", "")}: {check["status"]} — {check["reason"]}'
                    part += "\n" + tool["scope"]
                    for citation in tool["citations"]:
                        part += f' [{citation["id"]}]'
                        if citation["id"] not in seen:
                            seen.add(citation["id"]); citations.append(citation)
                    parts.append(part)
                return finish(status, "\n\n".join(parts), citations)
        # This data-availability gate also applies to the one-pass baseline.
        if route["missing_topic"]:
            return finish("insufficient_data", route["missing_topic"] + " Cần bổ sung nguồn đúng phạm vi.",
                          [c for c in chunks if c["kind"] in ("gap", "scope")])
        status, answer, used = self._compose(question, chunks, cohort, metrics)
        return finish(status, answer, used)

    @staticmethod
    def _usage(metrics, usage):
        for key in ("prompt_tokens", "completion_tokens", "embedding_tokens", "index_embedding_tokens"):
            metrics[key] += int(usage.get(key, 0))

    def _compose(self, question, chunks, cohort, metrics):
        requested = course_codes(question)
        found = {c.get("course_code") for c in chunks}
        if any(code not in self.catalog.courses for code in requested):
            return "insufficient_data", "Mã học phần chưa có trong danh mục đã xác minh: " + ", ".join(
                c for c in requested if c not in self.catalog.courses) + ". Cần bổ sung nguồn đúng khóa.", []
        if requested and any(code not in found for code in requested):
            return "insufficient_data", "Chưa truy xuất đủ học phần được hỏi; chưa đủ bằng chứng để trả lời toàn bộ.", chunks
        useful = [c for c in chunks if c["kind"] != "gap"]
        if not useful:
            text = "Chưa có bằng chứng đủ để trả lời. " + " ".join(c["text"] + f' [{c["id"]}]' for c in chunks)
            return "insufficient_data", text, chunks
        if self.provider:
            output, usage = self.provider.generate(question, chunks, cohort)
            self._usage(metrics, usage)
            if not validate_generation(output, chunks):
                return "insufficient_data", "Không hiển thị kết luận: LLM trả trích dẫn hoặc trích đoạn không hợp lệ.", []
            claims = output["claims"]
            text = "\n\n".join(c["text"] + f' [{c["evidence_id"]}]' for c in claims)
            if output.get("clarification"):
                text += "\n\n" + output["clarification"]
            used_ids = {c["evidence_id"] for c in claims}
            return output["status"], text.strip(), [c for c in chunks if c["id"] in used_ids]
        # Offline mode is an extractive plumbing demo, not an LLM experiment.
        selected = [c for c in useful if c.get("course_code") in requested] if requested else useful
        text = "Các đoạn tìm được (chế độ trích xuất, chưa tổng hợp bằng LLM):\n\n" + "\n\n".join(
            c["text"] + f' [{c["id"]}]' for c in selected)
        status = "evidence_found" if selected else "insufficient_data"
        return status, text, selected
