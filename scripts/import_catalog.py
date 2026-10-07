"""Rebuild runtime JSON from the project workbook without inferring blank fields.

Requires openpyxl only for this import step; server/tests use the standard library.
"""
import argparse
import hashlib
import json
from datetime import date, datetime
from pathlib import Path


def convert(workbook_path, destination):
    from openpyxl import load_workbook

    path, out = Path(workbook_path), Path(destination)
    workbook = load_workbook(path, data_only=True)

    def rows(sheet):
        return [list(row) for row in list(workbook[sheet].values)[4:] if row[0]]

    def scalar(value):
        return value.isoformat()[:10] if isinstance(value, (date, datetime)) else value

    sources = []
    for row in rows("Nguon"):
        keys = ("id", "title", "issued_at", "effective_at", "published_at", "scope_text",
                "usability", "locator", "url", "file_url", "limitations")
        item = dict(zip(keys, map(scalar, row)))
        item["applicable"] = item["id"] in ("S01", "S02", "S03", "S04")
        item["cohorts"] = ["K37"] if item["applicable"] else []
        item["content_level"] = "inventory_summary"
        sources.append(item)

    courses = []
    for row in rows("Hoc phan"):
        item = dict(zip(("code", "name", "credits", "group", "selection_rule", "prerequisite_raw",
                         "prerequisite_status", "page", "hours", "factor", "source_row_count",
                         "source_rows", "limitations"), row))
        if item["prerequisite_status"] == "SOURCE_BLANK":
            item["prerequisite_raw"] = None
        item.update(source_id="S01", cohort="K37", version="24081902/2024",
                    verification="VERIFIED_TRANSCRIPTION", current_amendments_verified=False)
        courses.append(item)

    conditions = []
    for row in rows("Dieu kien"):
        conditions.append(dict(zip(("id", "course", "kind", "reference", "operator", "threshold",
                                    "quote", "status", "page", "limitations"), row)))
    gaps = [dict(zip(("id", "topic", "status", "details", "needed_evidence"), r))
            for r in rows("Can xac minh")]
    out.mkdir(parents=True, exist_ok=True)
    payloads = {"sources": sources, "courses": courses, "conditions": conditions,
                "gaps": gaps, "raw_rows": rows("Dong nguon")}
    for name, data in payloads.items():
        (out / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {"dataset": "project", "cohort": "K37", "program": "CNTT",
                "snapshot_date": "2026-10-07", "workbook": path.name,
                "workbook_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "source_library_id": "libfile_f0edc7d8338c81919eebfb0454ec4a08",
                "course_count": len(courses), "raw_row_count": len(payloads["raw_rows"]),
                "condition_count": len(conditions), "original_documents_ingested": False,
                "amendments_verified": False}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook")
    parser.add_argument("--output", default="data/project")
    args = parser.parse_args()
    print(json.dumps(convert(args.workbook, args.output), ensure_ascii=False))
