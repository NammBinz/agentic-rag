"""OCR scanned PDFs downloaded by TLU_Notice_Tool with Gemini, keeping page markers and tables.

Reads <data>/approved/*/metadata.json, picks PDFs whose text layer is empty, de-duplicates by
sha256 and writes <data>/files/<sha256>.ocr.md plus <data>/ocr_manifest.json. The transcript is
verbatim text for later review, not verified content. Requires pypdf and GEMINI_API_KEY.
"""
import argparse
import base64
import datetime
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from agentic_rag.server import load_env

PROMPT = """Đây là trang {first}–{last} của một văn bản hành chính tiếng Việt (bản scan) của Trường Đại học Thăng Long.
Hãy chép lại NGUYÊN VĂN toàn bộ nội dung theo thứ tự đọc. Quy tắc:
- Mở đầu mỗi trang bằng một dòng riêng: <!-- trang N --> (N là số trang trong tệp gốc, bắt đầu từ {first}).
- Giữ nguyên tiêu đề, số hiệu, "Chương", "Điều", "Khoản", điểm a/b/c và cách xuống dòng của danh sách.
- Bảng chép thành bảng Markdown, giữ đủ hàng và cột; ô gộp thì lặp lại giá trị hoặc để trống, không bỏ hàng.
- Không tóm tắt, không giải thích, không thêm nội dung, không sửa lỗi chính tả của văn bản gốc.
- Chữ không đọc rõ ghi [không đọc rõ]; chữ ký ghi [chữ ký]; con dấu ghi [con dấu].
Chỉ trả về nội dung đã chép."""


def call_gemini(pdf_bytes, first, last, model, key, retries=4):
    body = {"contents": [{"parts": [
        {"inline_data": {"mime_type": "application/pdf", "data": base64.b64encode(pdf_bytes).decode()}},
        {"text": PROMPT.format(first=first, last=last)}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 32768}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    for attempt in range(retries + 1):
        request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                data = json.load(response)
            candidate = data["candidates"][0]
            text = "".join(p.get("text", "") for p in candidate.get("content", {}).get("parts", []))
            return text, candidate.get("finishReason"), data.get("usageMetadata", {})
        except urllib.error.HTTPError as error:
            if error.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(min(60, 5 * 2 ** attempt))
                continue
            raise RuntimeError(f"Gemini HTTP {error.code}") from None
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries:
                time.sleep(min(60, 5 * 2 ** attempt))
                continue
            raise


def page_range(reader, start, end):
    from pypdf import PdfWriter
    writer = PdfWriter()
    for i in range(start, end):
        writer.add_page(reader.pages[i])
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


MARK = re.compile(r"<!-- trang (\d+) -->")
MISSING = "[CHƯA OCR ĐƯỢC — đối chiếu bản scan]"


def split_pages(text):
    """Map page number -> transcript using the page markers the model was asked to emit."""
    pieces = MARK.split(text)
    pages = {}
    for number, body in zip(pieces[1::2], pieces[2::2]):
        if body.strip() and MISSING not in body:
            pages[int(number)] = body.strip()
    return pages


def ocr_file(path, model, key, per_call, pause, fallback, pages=None):
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    total, usage, warnings = len(reader.pages), {"prompt": 0, "output": 0}, []
    pages = dict(pages or {})

    def run(start, end, use_model):
        text, finish, meta = call_gemini(page_range(reader, start, end), start + 1, end, use_model, key)
        usage["prompt"] += meta.get("promptTokenCount", 0)
        usage["output"] += meta.get("candidatesTokenCount", 0)
        found = {n: t for n, t in split_pages(text).items() if start < n <= end}
        if end - start == 1 and not found and finish == "STOP" and text.strip():
            found = {end: text.strip()}  # A single page answered without its marker.
        print(f"   trang {start + 1}-{end}/{total} {use_model} {finish} ({len(found)} trang)", flush=True)
        time.sleep(pause)
        return found, finish

    try:
        fill(run, pages, total, per_call, model, fallback, warnings)
    except Exception as error:
        # Keep pages finished before a quota/network error so the next --repair run resumes there.
        error.partial_text = render(pages, total)
        raise
    missing = [n for n in range(1, total + 1) if n not in pages]
    return render(pages, total), total, usage, warnings, missing


def render(pages, total):
    return "\n\n".join(f"<!-- trang {n} -->\n" + pages.get(n, MISSING) for n in range(1, total + 1)) + "\n"


def fill(run, pages, total, per_call, model, fallback, warnings):
    start = 0
    while start < total:
        end = min(total, start + per_call)
        if all(n in pages for n in range(start + 1, end + 1)):
            start = end
            continue
        found, finish = run(start, end, model)
        if finish == "MAX_TOKENS" and end - start > 1:
            per_call = max(1, (end - start) // 2)  # Too dense for one call: retry with fewer pages.
            continue
        pages.update(found)
        start = end
    # Pages dropped or blocked (e.g. RECITATION) are retried one at a time, then with the fallback model.
    for number in range(1, total + 1):
        for use_model in dict.fromkeys([model, fallback]):
            if number in pages or not use_model:
                continue
            found, finish = run(number - 1, number, use_model)
            pages.update(found)
            if number not in pages:
                warnings.append(f"trang {number}: {use_model} {finish}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, type=Path, help="Thư mục data của TLU_Notice_Tool")
    parser.add_argument("--model", default=None)
    parser.add_argument("--only", help="Chỉ xử lý sha256 bắt đầu bằng chuỗi này")
    parser.add_argument("--pages-per-call", type=int, default=4)
    parser.add_argument("--pause", type=float, default=4.0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--repair", action="store_true", help="Chỉ OCR lại các trang còn thiếu của tệp đã làm")
    parser.add_argument("--fallback-model", default=None, help="Model thử lại cho trang bị chặn/thiếu")
    parser.add_argument("--redo", action="append", default=[], metavar="SHA_PREFIX:1,2,3",
                        help="OCR lại từng trang chỉ định (ví dụ trang bị lẫn nội dung trang khác)")
    args = parser.parse_args()
    load_env(ROOT / ".env")
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        sys.exit("Thiếu GEMINI_API_KEY")
    model = args.model or os.getenv("GEMINI_OCR_MODEL") or os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite"
    fallback = args.fallback_model or os.getenv("GEMINI_OCR_FALLBACK") or "gemini-3.5-flash"

    targets = {}
    for meta_path in sorted(args.data.glob("approved/*/metadata.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for f in meta["files"]:
            if f["path"].lower().endswith(".pdf") and "ít/không có chữ" in f["status"]:
                targets.setdefault(f["sha256"], {"path": f["path"], "notices": []})["notices"].append(
                    {"id": meta["id"], "title": meta["title"]})
    manifest_path = args.data / "ocr_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    for sha, target in targets.items():
        if args.only and not sha.startswith(args.only):
            continue
        out = args.data / "files" / f"{sha}.ocr.md"
        previous = manifest.get(sha, {})
        redo = {int(n) for spec in args.redo if sha.startswith(spec.split(":")[0]) for n in spec.split(":")[1].split(",")}
        complete = previous.get("status") == "done" and not previous.get("missing_pages") and "missing_pages" in previous
        if out.exists() and not args.force and not redo and (complete or (previous.get("status") == "done" and not args.repair)):
            continue
        known = split_pages(out.read_text(encoding="utf-8")) if out.exists() and not args.force else {}
        # Multi-page calls can mix up pages; redone pages are always read one page per call.
        known = {n: t for n, t in known.items() if n not in redo}
        print(f"OCR {sha[:10]} — {target['notices'][0]['title'][:70]} (đã có {len(known)} trang)", flush=True)
        try:
            text, pages, usage, warnings, missing = ocr_file(args.data / target["path"].replace("\\", "/"), model,
                                                             key, 1 if redo else args.pages_per_call, args.pause,
                                                             fallback, known)
            out.write_text(text, encoding="utf-8")
            old_usage = previous.get("usage_tokens", {"prompt": 0, "output": 0})
            usage = {k: usage[k] + old_usage.get(k, 0) for k in usage}
            manifest[sha] = {"status": "done", "pages": pages, "missing_pages": missing, "model": model,
                             "fallback_model": fallback, "usage_tokens": usage,
                             "warnings": warnings, "notices": target["notices"], "output": out.name,
                             "ocr_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                             "note": "Bản chép OCR tự động; cần đối chiếu số liệu với bản scan trước khi dùng."}
        except Exception as error:
            if getattr(error, "partial_text", None):
                out.write_text(error.partial_text, encoding="utf-8")
            manifest[sha] = {"status": "error", "error": str(error), "notices": target["notices"]}
            print("   lỗi:", error, flush=True)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            if "429" in str(error):
                print("Hết hạn mức của model; dừng, chạy lại --repair sau.", flush=True)
                break
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    done = [m for m in manifest.values() if m.get("status") == "done"]
    print(f"Xong {len(done)}/{len(targets)} tệp; token vào {sum(m['usage_tokens']['prompt'] for m in done)}, "
          f"ra {sum(m['usage_tokens']['output'] for m in done)}.")


if __name__ == "__main__":
    main()
