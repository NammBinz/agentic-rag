"""Rebuild runtime JSON from the project workbook without inferring blank fields.

Requires openpyxl only for this import step; server/tests use the standard library.
"""
import argparse
import hashlib
import json
from datetime import date, datetime
from pathlib import Path


def convert(workbook_path, destination, library_file_id=None):
    from openpyxl import load_workbook

    path, out = Path(workbook_path), Path(destination)
    workbook = load_workbook(path, data_only=True)

    required = ('Hoc phan', 'Dieu kien', 'Nguon', 'Can xac minh', 'Dong nguon')
    if not all(name in workbook.sheetnames for name in required):
        raise ValueError('Thiếu tab bắt buộc của snapshot K37')
    def rows(sheet):
        return [list(row) for row in list(workbook[sheet].values)[4:] if row[0]]
    def locations(sheet):
        return [i for i, row in enumerate(list(workbook[sheet].values)[4:], 5) if row[0]]

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
    expected = (len(courses), len({c['code'] for c in courses}), len(conditions),
                len(rows('Dong nguon')), sum(c['prerequisite_status'] == 'SOURCE_BLANK' for c in courses))
    if expected != (99, 99, 76, 100, 31):
        raise ValueError(f'Snapshot không khớp mốc K37 99/99/76/100/31: {expected}')
    for record, row in zip(courses, locations('Hoc phan')):
        record.update(workbook_sheet='Hoc phan', workbook_row=row)
    for record, row in zip(conditions, locations('Dieu kien')):
        record.update(workbook_sheet='Dieu kien', workbook_row=row)
    for record, row in zip(sources, locations('Nguon')):
        record.update(workbook_sheet='Nguon', workbook_row=row)
    out.mkdir(parents=True, exist_ok=True)
    payloads = {"sources": sources, "courses": courses, "conditions": conditions,
                "gaps": gaps, "raw_rows": rows("Dong nguon"),
                "workbook_snapshot": {s.title: {'header_row': 4,
                    'headers': [scalar(v) for v in list(s.values)[3]],
                    'records': [{'excel_row': i, 'values': [scalar(v) for v in row]}
                                for i, row in enumerate(list(s.values)[4:], 5) if row[0]]}
                    for s in workbook}}
    for name, data in payloads.items():
        (out / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {"dataset": "project", "cohort": "K37", "program": "CNTT",
                "snapshot_date": "2026-10-07", "workbook": path.name,
                "workbook_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "source_library_id": library_file_id,
                "tabs_present": workbook.sheetnames, "source_count": len(sources),
                "source_blank_count": 31,
                "expected_checkpoint_sha256": "ff3f55329e47175d8c842dd23c77169d85a0805ae3acb5d6cd4cf52002d4587a",
                "checkpoint_workbook_matches": hashlib.sha256(path.read_bytes()).hexdigest() == "ff3f55329e47175d8c842dd23c77169d85a0805ae3acb5d6cd4cf52002d4587a",
                "provenance_note": f"Bản nhập có {len(workbook.sheetnames)} tab/{len(sources)} nguồn. Đối chiếu workbook_sha256; không coi là bản 9 tab/25 nguồn nếu hash khác mốc 24/10. Không tái xác minh website/PDF.",
                "course_count": len(courses), "raw_row_count": len(payloads["raw_rows"]),
                "condition_count": len(conditions), "original_documents_ingested": False,
                "amendments_verified": False}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    from migrate_scope import upgrade
    upgrade(out)
    return json.loads((out / "manifest.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook")
    parser.add_argument("--output", default="data/project")
    parser.add_argument("--library-file-id", default=None)
    args = parser.parse_args()
    print(json.dumps(convert(args.workbook, args.output, args.library_file_id), ensure_ascii=False))
