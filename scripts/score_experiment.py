"""Automatic proxy scores for run_experiment.py output, grouped by mode and question group.

These are rule-based proxies (outcome category, required/forbidden terms, cited source IDs).
They do not replace human grading of correctness and of whether each claim is supported.
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agentic_rag.catalog import normalize

OUTCOMES = {
    "answered": "answer", "evidence_found": "answer", "recorded_conditions": "answer",
    "catalog_summary": "answer", "satisfied_in_snapshot": "answer", "not_met_in_snapshot": "answer",
    "mixed_results": "answer", "insufficient_data": "abstain", "not_found": "abstain",
    "out_of_scope": "refuse", "needs_input": "needs_input",
}


def _matches(text, phrase):
    # Word boundaries keep "12" from matching inside "112" or "3 TC" inside "13 TC".
    return re.finditer(r"(?<![a-z0-9])" + re.escape(normalize(phrase)) + r"(?![a-z0-9])", normalize(text))


def contains(text, phrase):
    return next(_matches(text, phrase), None) is not None


# "không thể kết luận là không có tiên quyết" rejects the forbidden claim instead of making it.
NEGATION_CUES = ("khong the ket luan", "chua the ket luan", "khong duoc chuyen thanh", "khong chuyen thanh",
                 "khong co nghia la", "khong phai la", "khong dong nghia", "khong duoc hieu la", "khong hieu la")


def asserts(text, phrase):
    normalized = normalize(text)
    return any(not any(cue in normalized[max(0, m.start() - 40):m.start()] for cue in NEGATION_CUES)
               for m in _matches(normalized, phrase))


def score_run(run):
    gold, result = run["gold"], run.get("result") or {}
    row = {"id": run["id"], "mode": run["mode"], "group": run.get("group"), "error": run["run_status"] == "error",
           "skipped": run["run_status"] == "skipped"}
    if row["error"] or row["skipped"]:
        return row
    text = normalize(result.get("answer") or "")
    outcome = OUTCOMES.get(result.get("status"), "other")
    expected = gold.get("gold_outcome")
    accepted = set(expected) if isinstance(expected, list) else {expected}
    # Refusing out-of-scope via a clarifying question is also safe behaviour.
    row["outcome_ok"] = outcome in accepted or ("refuse" in accepted and outcome == "needs_input")
    if gold.get("gold_status"):
        row["status_ok"] = result.get("status") == gold["gold_status"]
    terms = gold.get("gold_required_terms") or []
    if terms:
        hits = sum(any(contains(text, alt) for alt in alternatives) for alternatives in terms)
        row["term_recall"] = hits / len(terms)
        row["all_terms"] = hits == len(terms)
    row["forbidden_hit"] = any(asserts(text, f) for f in gold.get("gold_forbidden_terms") or [])
    cited = {c["id"] for c in result.get("citations", [])}
    sources = set(gold.get("gold_sources") or [])
    if sources and "answer" in accepted:
        row["source_recall"] = len(sources & cited) / len(sources)
        if cited:
            row["citation_precision"] = len(sources & cited) / len(cited)
    # Items that accept both answering and abstaining are left out of abstention metrics.
    refusals = {"abstain", "refuse", "needs_input"}
    row["abstain_expected"] = None if accepted & refusals and accepted - refusals else bool(accepted <= refusals)
    row["abstained"] = outcome in ("abstain", "refuse", "needs_input")
    metrics = result.get("metrics", {})
    row["latency_ms"] = metrics.get("latency_ms")
    row["tokens"] = metrics.get("prompt_tokens", 0) + metrics.get("completion_tokens", 0)
    row["api_retries"] = metrics.get("api_retries", 0)
    return row


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def summarize(rows):
    done = [r for r in rows if not r["error"] and not r["skipped"]]
    decided = [r for r in done if r["abstain_expected"] is not None]
    expected = [r for r in decided if r["abstain_expected"]]
    predicted = [r for r in decided if r["abstained"]]
    both = [r for r in expected if r["abstained"]]
    return {
        "n": len(rows), "errors": sum(r["error"] for r in rows), "skipped": sum(r["skipped"] for r in rows),
        "outcome_acc": mean([float(r["outcome_ok"]) for r in done]),
        "status_acc": mean([float(r["status_ok"]) for r in done if "status_ok" in r]),
        "term_recall": mean([r.get("term_recall") for r in done]),
        "all_terms": mean([float(r["all_terms"]) for r in done if "all_terms" in r]),
        "forbidden_rate": mean([float(r["forbidden_hit"]) for r in done]),
        "source_recall": mean([r.get("source_recall") for r in done]),
        "citation_precision": mean([r.get("citation_precision") for r in done]),
        "abstain_precision": len(both) / len(predicted) if predicted else None,
        "abstain_recall": len(both) / len(expected) if expected else None,
        "latency_ms": mean([r["latency_ms"] for r in done]),
        "tokens": mean([r["tokens"] for r in done]),
        "api_retries": sum(r.get("api_retries") or 0 for r in done),
    }


COLUMNS = ["n", "errors", "outcome_acc", "status_acc", "term_recall", "all_terms", "forbidden_rate",
           "source_recall", "citation_precision", "abstain_precision", "abstain_recall", "latency_ms", "tokens",
           "api_retries"]


def fmt(value):
    if value is None:
        return "–"
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def table(title, summaries):
    lines = [f"### {title}", "", "| nhóm | " + " | ".join(COLUMNS) + " |", "|---" * (len(COLUMNS) + 1) + "|"]
    for key, summary in summaries.items():
        lines.append(f"| {key} | " + " | ".join(fmt(summary[c]) for c in COLUMNS) + " |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", help="JSONL từ run_experiment.py")
    parser.add_argument("--output", help="Ghi báo cáo Markdown (mặc định in ra màn hình)")
    parser.add_argument("--gold", help="Chấm theo nhãn hiện tại của bộ đánh giá thay vì nhãn lưu lúc chạy")
    args = parser.parse_args()
    runs = [json.loads(line) for line in Path(args.runs).read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.gold:
        # Re-scoring after a label revision must not require new API calls.
        items = {q["id"]: q for q in map(json.loads, Path(args.gold).read_text(encoding="utf-8").splitlines()) if q}
        for run in runs:
            if run["id"] in items:
                run["gold"] = {k: v for k, v in items[run["id"]].items() if k.startswith("gold_")}
    rows = [score_run(r) for r in runs]
    by_mode = defaultdict(list)
    for row in rows:
        by_mode[row["mode"]].append(row)
    parts = ["# Điểm tự động (proxy)", "",
             "Chỉ là chỉ số quy tắc: nhóm kết quả, từ khóa bắt buộc/cấm và ID nguồn. "
             "Không thay chấm tay độ đúng và tính hỗ trợ của từng kết luận. "
             "Nhóm catalog_* dùng chung công cụ thống kê ở rag và agent; so sánh riêng.", ""]
    parts.append(table("Tổng theo chế độ", {m: summarize(r) for m, r in sorted(by_mode.items())}))
    for mode, mode_rows in sorted(by_mode.items()):
        groups = defaultdict(list)
        for row in mode_rows:
            groups[row["group"]].append(row)
        parts += ["", table(f"Chế độ {mode} theo nhóm", {g: summarize(r) for g, r in sorted(groups.items())})]
    failures = [r for r in rows if not r.get("error") and not r.get("skipped") and
                (not r.get("outcome_ok") or r.get("all_terms") is False or r.get("forbidden_hit"))]
    parts += ["", f"### Ca cần xem lại ({len(failures)})", ""]
    parts += [f"- {r['mode']} {r['id']}: outcome_ok={r.get('outcome_ok')}, term_recall={fmt(r.get('term_recall'))}, "
              f"forbidden={r.get('forbidden_hit')}" for r in failures]
    report = "\n".join(parts) + "\n"
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Đã ghi {args.output}")
    else:
        sys.stdout.write(report)


if __name__ == "__main__":
    main()
