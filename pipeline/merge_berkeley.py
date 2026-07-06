#!/usr/bin/env python3
"""
Merge the Berkeley HSP appendix CSVs (data/berkeley_appendix/*.csv) into the
master data/ordinances.csv.

The appendix column names may differ from ours; edit COLUMN_MAP after
inspecting the downloaded tabs. Rows are deduplicated on
(jurisdiction, code_section).
"""
import csv
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
MASTER = DATA / "ordinances.csv"
APPENDIX_DIR = DATA / "berkeley_appendix"

MASTER_FIELDS = [
    "jurisdiction", "jurisdiction_type", "county", "code_section",
    "ordinance_name", "category", "summary", "status",
    "date_enacted_or_amended", "penalty", "source", "verification_status",
]

# Map appendix headers (lowercased, stripped) -> master fields.
# EDIT after inspecting the real tabs.
COLUMN_MAP = {
    "jurisdiction": "jurisdiction",
    "city": "jurisdiction",
    "city/county": "jurisdiction",
    "county": "county",
    "ordinance": "code_section",
    "code section": "code_section",
    "municipal code": "code_section",
    "law": "ordinance_name",
    "title": "ordinance_name",
    "type": "category",
    "category": "category",
    "description": "summary",
    "summary": "summary",
    "notes": "summary",
    "status": "status",
    "date": "date_enacted_or_amended",
    "date enacted": "date_enacted_or_amended",
    "penalty": "penalty",
    "source": "source",
    "link": "source",
}


def load_master() -> dict[tuple, dict]:
    rows = {}
    with open(MASTER, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows[(row["jurisdiction"].lower(), row["code_section"].lower())] = row
    return rows


def main() -> None:
    master = load_master()
    added = 0
    for path in sorted(APPENDIX_DIR.glob("*.csv")):
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for raw in reader:
                row = {k: "" for k in MASTER_FIELDS}
                for col, val in raw.items():
                    key = (col or "").strip().lower()
                    if key in COLUMN_MAP and val:
                        tgt = COLUMN_MAP[key]
                        row[tgt] = f"{row[tgt]} | {val}".strip(" |") if row[tgt] else val
                if not row["jurisdiction"]:
                    continue
                row["jurisdiction_type"] = row["jurisdiction_type"] or "city"
                row["source"] = row["source"] or f"Berkeley HSP appendix ({path.name})"
                row["verification_status"] = "berkeley_hsp_appendix"
                key = (row["jurisdiction"].lower(), row["code_section"].lower())
                if key not in master:
                    master[key] = row
                    added += 1
    with open(MASTER, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MASTER_FIELDS)
        w.writeheader()
        for row in sorted(master.values(), key=lambda r: (r["county"], r["jurisdiction"])):
            w.writerow({k: row.get(k, "") for k in MASTER_FIELDS})
    print(f"Merged {added} new rows into {MASTER} ({len(master)} total).")


if __name__ == "__main__":
    main()
