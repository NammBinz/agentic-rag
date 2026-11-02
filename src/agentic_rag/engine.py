"""One-pass baseline; the bounded Agent is added as a separate orchestration path."""
import json
import os
import time
from .catalog import Catalog, course_codes, SUPPORTED_COHORTS, normalize
import re
from .provider import Settings, create_provider
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
        self.provider = provider if provider is not None else create_provider(self.settings)
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
                   "index_embedding_tokens": 0, "api_retries": 0, "estimated_cost_usd": None}
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
                route['intent'] in ('lookup', 'prerequisites', 'conditions', 'catalog_summary') or course_codes(question)):
            return finish("insufficient_data", self.catalog.context['message'])
        if route['intent'] == 'catalog_summary':
            result['actions'].append({'action': 'route', **route})
            query = route['catalog_query']
            if not options.get('enable_tools', True):
                return finish('insufficient_data', 'Câu hỏi này cần công cụ thống kê toàn bộ danh mục. Công cụ đang tắt; không thể đếm hoặc liệt kê đầy đủ bằng vài đoạn truy xuất.')
            if query.get('needs_context'):
                return finish('needs_input', 'Bạn muốn đếm hoặc liệt kê tất cả học phần K37, các môn bắt buộc hay một nhóm cụ thể? Hãy nêu nhóm cần tra.')
            tool = self.tools.catalog_summary(cohort, query['subset'], query.get('group'))
            result['tool_results'].append(tool)
            metrics['tool_calls'] = 1
            result['actions'].append({'action': 'catalog_summary', 'status': tool['status'],
                                      'reason': f"Đọc toàn bộ danh mục {tool['catalog_count']} mã; kết quả {tool['count']} mã trong bộ lọc."})
            result['actions'].append({'action': 'stop', 'reason': 'Kết quả được tính trực tiếp từ bảng học phần đúng phạm vi, không dùng LLM để đếm.'})
            if tool['status'] != 'catalog_summary':
                return finish(tool['status'], tool['message'])
            answer = self._catalog_answer(tool, query['count_only'])
            return finish('catalog_summary', answer, tool['citations'])
        if mode == "agent":
            result["actions"].append({"action": "route", **route})
            if (route["needs_target"] and not route["missing_topic"]) or len(route["targets"]) > 4:
                return finish("needs_input", "Hãy chọn 1–4 mã học phần cần tra/kiểm tra.")
            question = route["resolved_question"]
        chunks, usage = self.retriever.search(question, cohort,
                                              source_ids=route["source_ids"] if mode == "agent" else None)
        self._usage(metrics, usage)
        metrics["retrieval_rounds"] = 1
        result["actions"].append({"action": "retrieve", "round": 1, "query": question,
                                  "chunk_ids": [c["id"] for c in chunks]})
        if mode == "agent":
            if options.get("enable_tools", True) and route["intent"] in ("lookup", "prerequisites", "conditions"):
                for target in route["targets"]:
                    if route['intent'] == 'conditions':
                        tool = self.tools.conditions(target, cohort, depth=route['trace_depth'])
                    elif route['intent'] == 'prerequisites':
                        tool = self.tools.prerequisites(target, cohort, profile)
                    else:
                        tool = self.tools.lookup(target, cohort)
                    metrics["tool_calls"] += 1
                    result["tool_results"].append(tool)
                    result["actions"].append({"action": tool["tool"], "target": target, "status": tool["status"]})
                    present = {c["id"] for c in chunks}
                    # First pass adds the target record; related records use one extra retrieval.
                    chunks += [c for c in tool['citations'] if c['id'] not in present
                               and (route['intent'] != 'conditions' or c.get('course_code') == target)]
            missing = missing_evidence(question, route["targets"], chunks, self.catalog,
                                       include_dependencies=(route['intent'] == 'prerequisites' or (route['intent'] == 'conditions' and route['trace_depth'] > 0)))
            # A chain request can need a grandparent record as well as an immediate reference.
            for tool in result['tool_results']:
                for node in tool.get('nodes', []):
                    code = node['course_code']
                    if code in self.catalog.courses and self.catalog.course_chunk_id(self.catalog.courses[code]) not in {c['id'] for c in chunks} and code not in missing:
                        missing.append(code)
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
            if route['intent'] == 'conditions' and result['tool_results']:
                parts, used = [], []
                present = {c['id'] for c in chunks}
                incomplete = False
                statuses = []
                for tool in result['tool_results']:
                    statuses.append(tool['status'])
                    lines = [tool['message']]
                    for node in tool.get('nodes', []):
                        course = self.catalog.courses[node['course_code']]
                        cid = self.catalog.course_chunk_id(course)
                        if cid not in present:
                            incomplete = True
                            continue
                        raw = node['prerequisite_raw']
                        lines.append(f"{node['course_code']} — {course['name']} ({course['credits']} tín chỉ). Điều kiện ghi trong nguồn: {raw if raw is not None else 'SOURCE_BLANK — ô trống, chưa đủ căn cứ kết luận'} [{cid}]")
                        for component in node['components']:
                            lines.append(f"• {component['quote']} ({component['kind']}; {component['status']})")
                        used.extend(c for c in chunks if c['id'] == cid)
                    lines.append(tool['scope'])
                    parts.append('\n'.join(lines))
                answer = '\n\n'.join(parts)
                status = 'insufficient_data' if incomplete or any(s != 'recorded_conditions' for s in statuses) else 'recorded_conditions'
                if incomplete:
                    answer += '\nChưa truy xuất đủ chuỗi trong giới hạn một lượt bổ sung; cần thu hẹp câu hỏi.'
                if self.provider and used:
                    generated_status, generated, citations = self._compose(question, used, cohort, metrics, result["actions"])
                    if generated_status == 'insufficient_data':
                        status = 'insufficient_data'
                    answer = generated + '\n\n' + answer
                return finish(status, answer, list({c['id']: c for c in used}.values()))
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
                answer = '\n\n'.join(parts)
                if self.provider and citations:
                    _, generated, _ = self._compose(question, citations, cohort, metrics, result["actions"])
                    answer = generated + '\n\nKết quả đối chiếu bằng công cụ (không xác nhận quyền đăng ký):\n' + answer
                return finish(status, answer, citations)
        # This data-availability gate also applies to the one-pass baseline.
        if route["missing_topic"]:
            return finish("insufficient_data", route["missing_topic"] + " Cần bổ sung nguồn đúng phạm vi.",
                          [c for c in chunks if c["kind"] in ("gap", "scope")])
        status, answer, used = self._compose(question, chunks, cohort, metrics, result["actions"])
        return finish(status, answer, used)

    def _catalog_answer(self, tool, count_only):
        context = tool['context']
        scope = f"{context['cohort']} — {context['curriculum_id']}"
        subset = tool['subset']
        selection = ('được ghi “Bắt buộc theo mục khung”' if subset == 'mandatory' else
                     'thuộc nhóm lựa chọn hoặc nhánh thay thế' if subset == 'choices' else 'trong danh mục')
        group = f" thuộc nhóm {tool['group']}" if tool['group'] else ''
        lines = [f"Theo bảng {scope}, có {tool['count']} mã học phần {selection}{group}.",
                 f"Toàn bộ danh mục {context['cohort']} có {tool['catalog_count']} mã học phần phân biệt; đây không phải số môn mỗi sinh viên phải học."]
        lines.append('Phân nhóm kết quả: ' + '; '.join(f"{g['group']}: {g['count']}" for g in tool['groups']) + '.')
        if not count_only:
            for g in tool['groups']:
                lines.append('\n' + g['group'] + f" ({g['count']} môn):")
                for c in tool['courses']:
                    if c['group'] == g['group']:
                        cid = self.catalog.course_chunk_id(c)
                        rule = f"; {c['selection_rule']}" if subset != 'mandatory' else ''
                        lines.append(f"• {c['code']} — {c['name']} ({c['credits']} tín chỉ){rule}. [{cid}]")
        if subset == 'mandatory' and tool['choice_groups']:
            lines.append('\nCác nhóm phải lựa chọn hoặc có nhánh thay thế được ghi riêng, không cộng tất cả thành môn bắt buộc:')
            for g in tool['choice_groups']:
                codes = ', '.join(g['codes']) if len(g['codes']) <= 2 else f"{g['count']} mã"
                c = self.catalog.courses[g['codes'][0]]
                lines.append(f"• {g['group']} ({codes}): {g['selection_rule']}. [{self.catalog.course_chunk_id(c)}]")
        lines.append(f"\nChỉ phản ánh bảng {context['curriculum_id']}; {context['message']} Không suy ra tổng tín chỉ tốt nghiệp hoặc quyền đăng ký từ thống kê này.")
        return '\n'.join(lines)

    @staticmethod
    def _usage(metrics, usage):
        for key in ("prompt_tokens", "completion_tokens", "embedding_tokens", "index_embedding_tokens", "api_retries"):
            metrics[key] += int(usage.get(key, 0))

    def _compose(self, question, chunks, cohort, metrics, actions=None):
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
            if actions is not None:
                actions.append({"action": "generate", "provider": self.settings.provider})
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
