"""Reproducible offline functionality checks using explicit synthetic inputs."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agentic_rag.engine import Engine
from agentic_rag.provider import Settings

CASES = [
    {"id": "rag-citation", "dataset": "sample", "question": "PY201 có bao nhiêu tín chỉ?", "mode": "rag", "cohort": "K37", "expect": "evidence_found", "citation": "COURSE-PY201", "rounds": 1},
    {"id": "agent-lookup", "dataset": "sample", "question": "Tra học phần PY201", "mode": "agent", "cohort": "K37", "expect": "evidence_found", "citation": "COURSE-PY201"},
    {"id": "and-satisfied", "dataset": "sample", "question": "Kiểm tra tiên quyết PY201", "mode": "agent", "cohort": "K37", "profile": {"completed": ["PY101"], "credits": 12}, "expect": "satisfied_in_snapshot"},
    {"id": "and-failed", "dataset": "sample", "question": "Kiểm tra tiên quyết PY201", "mode": "agent", "cohort": "K37", "profile": {"completed": [], "credits": 12}, "expect": "not_met_in_snapshot"},
    {"id": "or-satisfied", "dataset": "sample", "question": "Kiểm tra tiên quyết PY202", "mode": "agent", "cohort": "K37", "profile": {"completed": [], "grades": {"CS101": 7}}, "expect": "satisfied_in_snapshot"},
    {"id": "missing-profile", "dataset": "sample", "question": "Kiểm tra tiên quyết PY201", "mode": "agent", "cohort": "K37", "expect": "needs_input"},
    {"id": "missing-cohort", "dataset": "sample", "question": "Tra PY201", "mode": "agent", "expect": "needs_input", "rounds": 0},
    {"id": "extra-retrieval", "dataset": "sample", "question": "So sánh PY201 và CS101", "mode": "agent", "cohort": "K37", "enable_tools": False, "expect": "evidence_found", "top_k": 1, "rounds": 2, "citation": "COURSE-CS101"},
    {"id": "extra-disabled", "dataset": "sample", "question": "So sánh PY201 và CS101", "mode": "agent", "cohort": "K37", "enable_tools": False, "enable_extra_retrieval": False, "expect": "insufficient_data", "top_k": 1, "rounds": 1},
    {"id": "synthetic-policy", "dataset": "sample", "question": "Đăng ký tối đa bao nhiêu tín chỉ mỗi kỳ?", "mode": "rag", "cohort": "K37", "expect": "evidence_found", "citation": "TEST-REGISTRATION"},
    {"id": "project-bare-code", "dataset": "project", "question": "Kiểm tra tiên quyết IT320", "mode": "agent", "cohort": "K37", "profile": {"completed": ["CS122"]}, "expect": "insufficient_data"},
    {"id": "project-source-blank", "dataset": "project", "question": "Kiểm tra tiên quyết CS121", "mode": "agent", "cohort": "K37", "profile": {}, "expect": "insufficient_data"},
    {"id": "project-unknown-tuition", "dataset": "project", "question": "Học phí kỳ này là bao nhiêu?", "mode": "agent", "cohort": "K37", "expect": "insufficient_data"},
    {"id": "unverified-cohort", "dataset": "project", "question": "IT320", "mode": "agent", "cohort": "K38", "expect": "insufficient_data", "rounds": 0},
    {"id": "k35-shared-curriculum", "dataset": "sample", "question": "PY201", "mode": "rag", "cohort": "K35", "expect": "evidence_found", "citation": "COURSE-PY201", "rounds": 1},
    {"id": "k38-new-version", "dataset": "sample", "question": "PY201", "mode": "rag", "cohort": "K38", "expect": "evidence_found", "citation": "COURSE-PY201-V2", "rounds": 1},
    {"id": "k38-new-prerequisite", "dataset": "sample", "question": "Kiểm tra tiên quyết PY201", "mode": "agent", "cohort": "K38", "profile": {"completed": ["PY101"], "credits": 12}, "expect": "not_met_in_snapshot"},
    {"id": "k39-missing-curriculum", "dataset": "sample", "question": "PY201", "mode": "agent", "cohort": "K39", "expect": "insufficient_data", "rounds": 0},
    {"id": "k39-shared-policy", "dataset": "sample", "question": "Đăng ký tối đa bao nhiêu tín chỉ mỗi kỳ?", "mode": "rag", "cohort": "K39", "expect": "evidence_found", "citation": "TEST-REGISTRATION"},
    {"id": "question-cohort-conflict", "dataset": "sample", "question": "PY201 của K37", "mode": "agent", "cohort": "K38", "expect": "needs_input", "rounds": 0},
]


def main():
    folder = ROOT / ".runtime"
    folder.mkdir(exist_ok=True)
    results = []
    for original in CASES:
        case = dict(original); dataset = case.pop("dataset"); top_k = case.pop("top_k", 4)
        cid = case.pop("id"); expected = case.pop("expect"); rounds = case.pop("rounds", None); citation = case.pop("citation", None)
        result = Engine(dataset, Settings(top_k=top_k)).answer(**case)
        passed = result["status"] == expected and (rounds is None or result["metrics"]["retrieval_rounds"] == rounds)
        passed = passed and (not citation or citation in {c["id"] for c in result["citations"]})
        passed = passed and result["metrics"]["retrieval_rounds"] <= 2
        results.append({"id": cid, "passed": passed, "expected_status": expected, "result": result})
        print(f'{"PASS" if passed else "FAIL"} {cid}: {result["status"]}; retrieval={result["metrics"]["retrieval_rounds"]}')
    (folder / "smoke_results.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n", encoding="utf-8")
    print(f"{sum(r['passed'] for r in results)}/{len(results)} cases passed. Full traces: .runtime/smoke_results.jsonl")
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
