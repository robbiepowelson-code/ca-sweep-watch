#!/usr/bin/env python3
"""
Expand data/agencies.csv to all 482 incorporated California cities using the
Census Bureau gazetteer (run on your machine with internet).

    pip install requests
    python fetch_agency_list.py
"""
import csv
import io
import zipfile
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parent.parent / "data"
AGENCIES = DATA / "agencies.csv"
GAZ_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2024_Gazetteer/2024_gaz_place_06.txt"
)
FIELDS = [
    "agency_name", "jurisdiction_type", "county", "cpra_email",
    "cpra_portal_url", "pd_records_email", "status",
    "last_request_sent", "response_due", "notes",
]


def main() -> None:
    r = requests.get(GAZ_URL, timeout=120)
    r.raise_for_status()
    existing = {}
    with open(AGENCIES, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            existing[row["agency_name"].lower()] = row

    added = 0
    reader = csv.DictReader(io.StringIO(r.text), delimiter="\t")
    for row in reader:
        name = row["NAME"].strip()
        # Incorporated cities/towns only (skip CDPs — unincorporated areas
        # are covered by their county's sheriff).
        if name.endswith(" CDP"):
            continue
        base = (
            name.replace(" city", "").replace(" town", "").strip()
        )
        agency = f"City of {base}"
        if agency.lower() in existing:
            continue
        existing[agency.lower()] = {
            "agency_name": agency, "jurisdiction_type": "city",
            "county": "", "cpra_email": "", "cpra_portal_url": "",
            "pd_records_email": "", "status": "not_contacted",
            "last_request_sent": "", "response_due": "", "notes": "",
        }
        added += 1

    with open(AGENCIES, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for row in sorted(
            existing.values(),
            key=lambda r: (r["jurisdiction_type"], r["agency_name"]),
        ):
            w.writerow({k: row.get(k, "") for k in FIELDS})
    print(f"Added {added} cities; {len(existing)} agencies total.")


if __name__ == "__main__":
    main()
