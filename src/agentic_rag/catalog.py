"""Versioned catalog and paragraph-level evidence built from reviewed data."""
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def normalize(text):
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def course_codes(text):
    return list(dict.fromkeys(re.findall(r"\b[A-Z]{2}\d{3}\b", text.upper())))


class Catalog:
    def __init__(self, dataset="project", data_root=None):
        if dataset not in ("project", "sample"):
            raise ValueError("dataset phải là project hoặc sample")
        folder = (Path(data_root) if data_root else ROOT / "data") / dataset
        self.dataset = dataset
        def read(name):
            return json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
        self.manifest = read("manifest")
        self.sources = {s["id"]: s for s in read("sources")}
        self.courses = {c["code"]: c for c in read("courses")}
        if len(self.courses) != len(read("courses")):
            raise ValueError("Mã học phần trùng trong bảng chuẩn hóa")
        self.conditions = read("conditions")
        self.gaps = read("gaps")
        self.chunks = self._chunks()
        ids = [c["id"] for c in self.chunks]
        if len(ids) != len(set(ids)):
            raise ValueError("Mã đoạn nguồn trùng")
        serialized = json.dumps([self.manifest, self.sources, self.chunks, self.conditions], sort_keys=True, ensure_ascii=False)
        self.fingerprint = hashlib.sha256(serialized.encode()).hexdigest()

    def _chunks(self):
        chunks = []
        for course in self.courses.values():
            raw = course["prerequisite_raw"]
            text = (f'{course["code"]} — {course["name"]}. Tín chỉ: {course["credits"]}. '
                    f'Nhóm: {course["group"]}. Quy tắc lựa chọn: {course["selection_rule"]}. '
                    f'Tiên quyết ghi trong nguồn: {raw if raw is not None else "ô trống; chưa xác định"}.')
            if course.get("limitations"):
                text += " " + course["limitations"]
            chunks.append({"id": "COURSE-" + course["code"], "source_id": course["source_id"],
                           "kind": "course", "course_code": course["code"], "text": text,
                           "page": course["page"], "section": course.get("source_rows", course["code"]),
                           "cohort": course["cohort"], "version": course["version"],
                           "verification": course["verification"], "content_level": "transcribed_row"})
        for source in self.sources.values():
            if not source["applicable"]:
                continue
            text = (f'{source["title"]}. Phạm vi: {source["scope_text"]}. '
                    f'Hiệu lực: {source["effective_at"]}. {source["limitations"]}')
            chunks.append({"id": "SOURCE-" + source["id"], "source_id": source["id"], "kind": "scope",
                           "text": text, "page": None, "section": source["locator"], "cohort": "K37",
                           "version": str(source["effective_at"]), "verification": "INVENTORY_CHECKED",
                           "content_level": "inventory_summary"})
        for gap in self.gaps:
            chunks.append({"id": "GAP-" + gap["id"], "source_id": "INVENTORY", "kind": "gap",
                           "text": f'{gap["topic"]}: {gap["details"]} Cần bổ sung: {gap["needed_evidence"]}',
                           "page": None, "section": gap["id"], "cohort": "K37", "version": "2026-10-07",
                           "verification": "MISSING_OR_UNVERIFIED", "content_level": "inventory_summary"})
        # Sample paragraphs exist only in the synthetic dataset.
        if self.dataset == "sample":
            for chunk in self.manifest.get("paragraphs", []):
                chunks.append(chunk)
        return chunks

    def citation(self, chunk):
        source = self.sources.get(chunk["source_id"], {})
        return {**chunk, "source_title": source.get("title", "Danh mục dữ liệu project — mục cần xác minh"),
                "url": source.get("url"), "file_url": source.get("file_url"),
                "effective_at": source.get("effective_at"), "source_scope": source.get("scope_text"),
                "dataset": self.dataset,
                "evidence_note": ("Dữ liệu giả lập, không phải quy định TLU." if self.dataset == "sample" else
                                  "Trích đoạn bảng chuẩn hóa/danh mục; chưa nhập toàn văn PDF gốc.")}

    def select_courses(self, query):
        code = query.strip().upper()
        if code in self.courses:
            return [self.courses[code]]
        terms = normalize(query).split()
        if not terms:
            return []
        return [c for c in self.courses.values() if all(t in normalize(c["name"] + " " + c["code"]) for t in terms)]
