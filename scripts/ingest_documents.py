"""Turn downloaded/OCR'd TLU documents into cohort-scoped full-text chunks (data/project/documents.json).

Input is the TLU_Notice_Tool data folder (approved/<id>/metadata.json, files/<sha>.txt|.ocr.md).
Every document is mapped by hand below to a source and its applicable cohorts, as verified from the
document text or the reviewed source workbook. Regulations are chunked per Điều (long ones per
khoản); table-heavy documents per page. Pages the OCR could not read become gap records.
"""
import argparse
import datetime
import difflib
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_CHARS = 2200

# New sources (existing S03–S06 come from the workbook import). Cohorts verified from each text.
NEW_SOURCES = {
    "N01": dict(title="Quy định chuẩn đầu ra ngoại ngữ trình độ đại học (2026)", issued_at="2026-08-06",
                cohorts=["K38"], scope_text="Điều 2 QĐ: áp dụng từ khóa tuyển sinh 2025–2026 (Khóa 38); khóa trước giữ quy định riêng.",
                limitations="Bản đăng chưa ghi số quyết định; ngày theo ngày đăng thông báo."),
    "N02": dict(title="Quy định chuẩn đầu ra Tiếng Anh cho sinh viên đại học chính quy khóa ≥ 26 – QĐ 23042504/QĐ-ĐHTL",
                issued_at="2023-04-25", cohorts=["K35", "K36", "K37"],
                scope_text="Áp dụng khóa ≥ 26 (trừ Ngôn ngữ Anh); K38 trở đi theo quy định 2026 (N01).",
                limitations="Bản OCR từ ảnh quét; số hiệu đọc từ bản OCR và được dẫn lại trong QĐ TOEIC 2026."),
    "N03": dict(title="Mức thu học phí đại học chính quy năm học 2026–2027 – QĐ 26070801/QĐ-ĐHTL", issued_at="2026-07-08",
                cohorts=["K35", "K36", "K37", "K38"],
                scope_text="Phụ lục 1: các khóa ≤ 37; Phụ lục 2: khóa 38. Năm học 2026–2027.",
                limitations="Bản OCR từ ảnh quét; đối chiếu số tiền với văn bản gốc trước khi trả lời chắc chắn."),
    "N04": dict(title="Mức thu học phí Khóa 39 đại học chính quy (từ năm học 2026–2027)", issued_at="2026-05-19",
                cohorts=["K39"], scope_text="Điều 1 QĐ: học phí Khóa 39 bắt đầu từ năm học 2026–2027.",
                limitations="Bản đăng chưa ghi số quyết định; ngày theo ngày đăng thông báo."),
}
# notice id prefix -> (source id, short name for chunk headers, chunking mode, topics)
DOCUMENTS = {
    "679c069c": ("S03", "Quy chế đào tạo 2024 (QĐ 24081901/QĐ-ĐHTL)", "article", ["quy_che", "tot_nghiep"]),
    "a67ab1b2": ("S05", "Quy chế đào tạo 2025 (QĐ 25091102/QĐ-ĐHTL)", "article", ["quy_che", "tot_nghiep"]),
    "a6a5537b": ("S06", "Quy chế đào tạo 2026 (QĐ 26082003/QĐ-ĐHTL)", "article", ["quy_che", "tot_nghiep"]),
    "f2070e37": ("S04", "Quy định TOEIC quốc tế xét chuẩn đầu ra K36–K37", "article", ["toeic", "chuan_dau_ra"]),
    "3151e282": ("N01", "Quy định chuẩn đầu ra ngoại ngữ 2026 (K38)", "article", ["toeic", "chuan_dau_ra"]),
    "1f414c54": ("N02", "Quy định chuẩn đầu ra Tiếng Anh khóa ≥ 26 (QĐ 23042504)", "article", ["toeic", "chuan_dau_ra"]),
    "e914915c": ("N03", "Mức thu học phí 2026–2027 (QĐ 26070801)", "page", ["hoc_phi"]),
    "a9c110da": ("N04", "Mức thu học phí Khóa 39", "page", ["hoc_phi"]),
}
PAGE = re.compile(r"^\s*(?:<!-- trang (\d+) -->|\[Trang (\d+)\])\s*$")
ARTICLE = re.compile(r"^\s*\**\s*Điều\s+(\d+)\s*[.:]\**\s*(.*)$")
CHAPTER = re.compile(r"^\s*\**\s*(Chương\s+[IVXLC\d]+)\b\**\s*(.*)$", re.I)
# Only a standalone upper-case heading starts an appendix ("Phụ lục số 10 (kèm theo)" inside a sentence does not).
APPENDIX = re.compile(r"^\s*\**\s*PHỤ LỤC(?:\s+(?:SỐ\s+)?[\dIVX]+)?\s*\**\s*$")
# The attached regulation starts at its own title or the "(Ban hành kèm theo ...)" line.
ATTACHED = re.compile(r"^\s*\**\s*(?:QUY CHẾ|QUY ĐỊNH)\s*\**\s*$|^\s*\**\s*\(?\s*\**Ban hành kèm theo")
MISSING = "[CHƯA OCR ĐƯỢC"


def clean(text):
    text = text.replace("**", "")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def pages_of(text):
    """Yield (page number, line) pairs; lines before the first marker count as page 1."""
    page = 1
    for line in text.splitlines():
        m = PAGE.match(line)
        if m:
            page = int(m.group(1) or m.group(2))
            continue
        yield page, line


def quarantine_duplicates(text):
    """A regulation never repeats a page, so near-identical pages mean OCR read one page twice.

    The repeated text is kept once (on the earlier page) and the later copy is blanked, so no content
    is duplicated or lost; both page numbers are reported so the uncertain page can be checked.
    """
    parts = re.split(r"(<!-- trang \d+ -->)", text)
    bodies = {i: re.sub(r"\s+", " ", parts[i + 1])[:600] for i in range(1, len(parts) - 1, 2)}
    page_no = {i: int(re.search(r"\d+", parts[i]).group()) for i in bodies}
    blanked, pairs = set(), []
    for a in bodies:
        for b in bodies:
            if b > a and b not in blanked and min(len(bodies[a]), len(bodies[b])) > 200 and \
                    difflib.SequenceMatcher(None, bodies[a], bodies[b]).ratio() > 0.85:
                blanked.add(b)
                pairs.append(f"{page_no[a]}/{page_no[b]}")
    for i in blanked:
        parts[i + 1] = "\n" + MISSING + " — trùng nội dung trang khác]\n"
    return "".join(parts), sorted(page_no[i] for i in blanked), pairs


def split_long(body):
    """Split an over-long article at khoản boundaries ("1.", "2.") or blank lines."""
    if len(body) <= MAX_CHARS:
        return [body]
    pieces, current = [], ""
    for block in re.split(r"\n(?=\d+\.\s)|\n\n", body):
        if current and len(current) + len(block) > MAX_CHARS:
            pieces.append(current.strip())
            current = ""
        current += block + "\n"
    if current.strip():
        pieces.append(current.strip())
    return pieces


def by_article(text):
    sections, current, part, last_no, chapter = [], None, "Quyết định ban hành", 0, ""
    for page, line in pages_of(text):
        if MISSING in line:
            continue
        if APPENDIX.match(line):
            part, chapter = "Phụ lục", ""
        elif part == "Quyết định ban hành" and ATTACHED.match(line):
            part, last_no = "Văn bản kèm theo", 0
        chap = CHAPTER.match(line)
        if chap:
            chapter = (chap.group(1) + (" " + chap.group(2) if chap.group(2) else "")).strip()
        art = ARTICLE.match(line)
        if art and part != "Phụ lục":
            number = int(art.group(1))
            # Numbering restarts, or goes past the 3–4 articles a decision has: the attached text has begun.
            if part == "Quyết định ban hành" and (number <= last_no or number >= 4):
                part = "Văn bản kèm theo"
            last_no = number
            current = {"part": part, "chapter": chapter, "label": f"Điều {number}. {art.group(2).strip()}",
                       "pages": [page], "lines": []}
            sections.append(current)
            continue
        if current is None or (part == "Phụ lục" and current.get("part") != "Phụ lục"):
            current = {"part": part, "chapter": chapter, "label": part if part == "Phụ lục" else "Phần mở đầu",
                       "pages": [page], "lines": []}
            sections.append(current)
        if page not in current["pages"]:
            current["pages"].append(page)
        current["lines"].append(line)
    return sections


def by_page(text):
    sections = {}
    for page, line in pages_of(text):
        if MISSING in line:
            continue
        sections.setdefault(page, {"part": "", "chapter": "", "label": f"Trang {page}", "pages": [page], "lines": []})
        sections[page]["lines"].append(line)
    return list(sections.values())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--notices", required=True, type=Path, help="Thư mục data của TLU_Notice_Tool")
    parser.add_argument("--output", default=ROOT / "data" / "project" / "documents.json", type=Path)
    args = parser.parse_args()
    existing = {s["id"]: s for s in json.loads((ROOT / "data" / "project" / "sources.json").read_text(encoding="utf-8"))}
    ocr = json.loads((args.notices / "ocr_manifest.json").read_text(encoding="utf-8"))
    sources, chunks, gaps, inputs, seen_ids = [], [], [], [], set()
    for sid, info in NEW_SOURCES.items():
        sources.append({"id": sid, "title": info["title"], "issued_at": info["issued_at"], "effective_at": info["issued_at"],
                        "published_at": None, "scope_text": info["scope_text"], "usability": "DÙNG ĐƯỢC — TOÀN VĂN",
                        "locator": "Toàn văn trích từ tệp đính kèm thông báo", "url": None, "file_url": None,
                        "limitations": info["limitations"], "cohorts": info["cohorts"], "programs": ["CNTT"],
                        "scope_verified": True, "scope_status": "VERIFIED_FROM_TEXT",
                        "document_version": f"{sid}:{info['issued_at']}", "effective_from": info["issued_at"],
                        "effective_to": None, "curriculum_ids": [], "content_level": "full_text"})
    for prefix, (sid, short, mode, topics) in DOCUMENTS.items():
        meta_path = next(args.notices.glob(f"approved/TLU-{prefix}*/metadata.json"))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        file = meta["files"][0]
        base = args.notices / "files" / file["sha256"]
        ocr_path = base.with_name(base.name + ".ocr.md")
        source_path = ocr_path if ocr_path.exists() else base.with_name(base.name + ".txt")
        text = source_path.read_text(encoding="utf-8")
        is_ocr = source_path.suffix == ".md"
        suspect, pairs = [], []
        if is_ocr and mode == "article":
            text, suspect, pairs = quarantine_duplicates(text)
        source = existing.get(sid) or next(s for s in sources if s["id"] == sid)
        if sid in existing:
            # Attach the downloaded file link to the workbook source record for citation.
            source = dict(existing[sid], file_url=file["url"])
            sources.append(source)
        sections = by_article(text) if mode == "article" else by_page(text)
        for n, sec in enumerate(sections, 1):
            body = clean("\n".join(sec["lines"]))
            if len(body) < 40:
                continue
            context = " — ".join(x for x in (short, sec["part"] if mode == "article" else "", sec["chapter"]) if x)
            # Stable ids (part + article or page + piece) keep evaluation gold sources valid across rebuilds.
            article = re.match(r"Điều (\d+)", sec["label"])
            part_code = {"Quyết định ban hành": "QD", "Văn bản kèm theo": "VB", "Phụ lục": "PL"}.get(sec["part"], "TR")
            stem = f"DOC-{sid}-{part_code}-" + (f"D{article.group(1)}" if article else f"P{sec['pages'][0]}")
            for k, piece in enumerate(split_long(body), 1):
                label = sec["label"] + (f" (phần {k})" if k > 1 else "")
                chunk_id = f"{stem}-{k}"
                while chunk_id in seen_ids:
                    chunk_id += "b"  # The same article read twice (OCR overlap) stays distinguishable.
                seen_ids.add(chunk_id)
                chunks.append({"id": chunk_id, "source_id": sid, "kind": "regulation",
                               "text": f"{context} — {label}\n{piece}", "page": sec["pages"][0],
                               "section": label, "pages": sec["pages"], "topics": topics,
                               "version": source["document_version"],
                               "verification": "OCR_UNREVIEWED" if is_ocr else "TEXT_EXTRACTED",
                               "content_level": "full_text", "notice_id": meta["id"], "file_sha256": file["sha256"]})
        missing = sorted(set(ocr.get(file["sha256"], {}).get("missing_pages", []) if is_ocr else []) | set(suspect))
        if missing:
            gaps.append({"id": f"OCR-{sid}", "topic": f"Trang chưa đọc được: {short}",
                         "status": "CHƯA OCR ĐƯỢC",
                         "details": f"Các trang {', '.join(map(str, missing))} của tệp quét chưa có bản chép; nội dung các trang này chưa có trong kho."
                                    + (f" Cặp trang OCR trùng nội dung (giữ một bản, số trang có thể lệch): {', '.join(pairs)}." if pairs else ""),
                         "needed_evidence": "Chép tay hoặc đối chiếu bản gốc các trang trên.",
                         "cohorts": source["cohorts"], "programs": ["CNTT"]})
        inputs.append({"notice_id": meta["id"], "source_id": sid, "file": source_path.name,
                       "sha256": hashlib.sha256(text.encode()).hexdigest(), "ocr": is_ocr, "missing_pages": missing})
    payload = {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "inputs": inputs,
               "note": "Toàn văn trích/OCR tự động; số liệu cần đối chiếu bản gốc. Không sửa tay — sửa nguồn rồi chạy lại.",
               "sources": sources, "chunks": chunks, "gaps": gaps}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    by_source = {}
    for c in chunks:
        by_source[c["source_id"]] = by_source.get(c["source_id"], 0) + 1
    print(f"{len(chunks)} đoạn từ {len(DOCUMENTS)} văn bản -> {args.output}: {by_source}; {len(gaps)} mục thiếu trang")


if __name__ == "__main__":
    main()
