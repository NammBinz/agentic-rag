"""Export matched A/B/C runs; human grading remains separate from software tests."""
import argparse
import dataclasses
import datetime
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agentic_rag.engine import Engine
from agentic_rag.provider import Settings, ProviderError
from agentic_rag.server import load_env


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="JSONL: id, group, question, cohort, profile; answers in gold metadata")
    parser.add_argument("--output", default=".runtime/experiment.jsonl")
    parser.add_argument("--dataset", choices=["project", "sample"], default="project")
    parser.add_argument("--mode", choices=["all", "llm", "rag", "agent"], default="all")
    parser.add_argument("--planner", choices=["rules", "llm"], default="rules", help="Bộ lập kế hoạch cho chế độ agent")
    parser.add_argument("--no-tools", action="store_true")
    parser.add_argument("--no-extra-retrieval", action="store_true")
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    parser.add_argument("--allow-draft-test", action="store_true",
                        help="Chỉ dùng khi thử quy trình; kết quả test trên nhãn nháp không được báo cáo")
    parser.add_argument("--pause", type=float, default=0.0, help="Giây nghỉ giữa các lần chạy (tránh 429)")
    parser.add_argument("--rerun-errors", metavar="PREVIOUS_JSONL",
                        help="Giữ các lần chạy đã xong trong file cũ, chỉ chạy lại các lần lỗi")
    args = parser.parse_args()
    load_env(ROOT / ".env")
    settings = dataclasses.replace(Settings.from_env(), top_k=args.top_k)
    engine = Engine(args.dataset, settings, cache_dir=ROOT / ".runtime" / "vectors" / args.dataset)
    questions = [json.loads(line) for line in Path(args.input).read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.split != "all":
        questions = [q for q in questions if q.get("split", "dev") == args.split]
    test = [q for q in questions if q.get("split") == "test"]
    if any(q.get("gold_status") is None and q.get("gold_outcome") is None for q in test):
        raise ValueError("Tập test cần đáp án/nhãn chuẩn được kiểm tra trước khi chạy")
    if not args.allow_draft_test and any(q.get("review_status", "reviewed") == "draft" for q in test):
        raise ValueError("Tập test còn nhãn nháp (review_status=draft); duyệt nhãn trước khi chạy test")
    modes = ["llm", "rag", "agent"] if args.mode == "all" else [args.mode]
    kept = {}
    if args.rerun_errors:
        for line in Path(args.rerun_errors).read_text(encoding="utf-8").splitlines():
            previous = json.loads(line) if line.strip() else None
            if previous and previous["run_status"] != "error":
                kept[(previous["id"], previous["mode"])] = previous
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    # 'x' protects earlier experimental outputs from accidental overwrites.
    with out.open("x", encoding="utf-8") as stream:
        for q in questions:
            for mode in modes:
                if (q["id"], mode) in kept:
                    stream.write(json.dumps(kept[(q["id"], mode)], ensure_ascii=False) + "\n")
                    continue
                if args.pause:
                    time.sleep(args.pause)
                run = {"id": q["id"], "group": q.get("group"), "split": q.get("split", "dev"), "mode": mode,
                       "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(), "gold": {
                       k: v for k, v in q.items() if k.startswith("gold_")}, "human_grading": None,
                       "settings": {"planner": args.planner, "no_tools": args.no_tools, "no_extra_retrieval": args.no_extra_retrieval,
                                    "top_k": args.top_k}}
                try:
                    result = engine.answer(q["question"], mode=mode, cohort=q.get("cohort"), profile=q.get("profile"),
                                           history=q.get("history"), planner=args.planner if mode == "agent" else None, enable_tools=not args.no_tools, enable_extra_retrieval=not args.no_extra_retrieval)
                    run.update(result=result, run_status="skipped" if result["status"] == "unavailable" else "completed")
                except ProviderError as error:
                    run.update(run_status="error", error=str(error))
                stream.write(json.dumps(run, ensure_ascii=False) + "\n"); stream.flush()
    print(f"Saved {len(questions) * len(modes)} runs to {out} ({len(kept)} reused); automatic answer accuracy is not claimed.")


if __name__ == "__main__":
    main()
