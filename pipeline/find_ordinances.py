#!/usr/bin/env python3
"""
City-by-city municipal code researcher.

Walks every California jurisdiction (data/all_jurisdictions.csv, built from
the Census gazetteer and cross-checked against Wikipedia's List of
municipalities in California), looks each one up on Municode, and searches
its code of ordinances for homelessness-enforcement keywords: camping,
encampment, RVs, lodging, homeless, sleeping, personal-property storage.

Results append to data/ordinance_research.csv (the working spreadsheet)
with review_status=needs_review. Cities not hosted on Municode are logged
with source=not_on_municode so they can be checked on amlegal/qcode or the
city website. Progress is saved so the weekly Action works through all
~540 jurisdictions in batches.

    python find_ordinances.py --batch 80
"""
import argparse
import csv
import json
import re
import time
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "ordinance_research.csv"
PROGRESS = DATA / "research_progress.json"
API = "https://api.municode.com"
KEYWORDS = ["camping", "encampment", "recreational vehicle", "homeless",
            "lodging", "sleeping in public", "storage of personal property"]
FIELDS = ["jurisdiction", "jurisdiction_type", "source", "keyword",
          "code_section", "title", "snippet", "url", "found_date",
          "review_status"]


def clean(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def municode_clients():
    r = requests.get(f"{API}/Clients/stateAbbr?stateAbbr=CA", timeout=60)
    r.raise_for_status()
    return {c["ClientName"].strip().lower(): c["ClientID"] for c in r.json()}


def search(client_id, kw):
    r = requests.get(f"{API}/search", params={
        "clientId": client_id, "contentTypeId": "CODES", "searchText": kw,
        "pageNum": 1, "pageSize": 10, "sort": 0,
        "titlesOnly": "true", "isAutocomplete": "false"}, timeout=60)
    if r.status_code != 200:
        return []
    return r.json().get("Hits") or []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=80)
    args = ap.parse_args()

    juris_file = DATA / "all_jurisdictions.csv"
    if not juris_file.exists():
        print("all_jurisdictions.csv missing - run build_full_jurisdictions.py first")
        return
    juris = list(csv.DictReader(open(juris_file, encoding="utf-8")))
    start = 0
    if PROGRESS.exists():
        start = json.loads(PROGRESS.read_text()).get("index", 0)
    batch = juris[start:start + args.batch]
    if not batch:
        print("all jurisdictions processed; resetting for a fresh refresh pass")
        PROGRESS.write_text(json.dumps({"index": 0}))
        return

    clients = municode_clients()
    print(f"municode hosts {len(clients)} CA jurisdictions")
    today = __import__("datetime").date.today().isoformat()
    new_rows, done = [], 0
    for j in batch:
        name = j["name"]
        lookups = [name.lower()]
        if j["jurisdiction_type"] == "city":
            lookups.append(f"city of {name}".lower())
        cid = next((clients[k] for k in lookups if k in clients), None)
        done += 1
        if cid is None:
            new_rows.append({**dict.fromkeys(FIELDS, ""),
                             "jurisdiction": name,
                             "jurisdiction_type": j["jurisdiction_type"],
                             "source": "not_on_municode", "found_date": today,
                             "review_status": "check_city_website"})
            continue
        seen = set()
        for kw in KEYWORDS:
            try:
                hits = search(cid, kw)
            except Exception as e:
                print(f"  {name}: search failed ({e})")
                continue
            for h in hits:
                node = h.get("NodeId", "")
                if node in seen:
                    continue
                seen.add(node)
                title = clean(h.get("Title"))
                m = re.match(r"(?:Sec(?:tion)?\.?\s*)?([\d][\d.\-]*)", title)
                sec = m.group(1) if m else ""
                slug = name.lower().replace(" ", "_")
                new_rows.append({
                    "jurisdiction": name,
                    "jurisdiction_type": j["jurisdiction_type"],
                    "source": "municode", "keyword": kw,
                    "code_section": sec, "title": title,
                    "snippet": clean(h.get("ContentFragment"))[:300],
                    "url": (f"https://library.municode.com/ca/{slug}/codes/"
                            f"code_of_ordinances?nodeId={node}"),
                    "found_date": today, "review_status": "needs_review"})
            time.sleep(0.4)
        print(f"  {name}: {len(seen)} sections flagged")

    exists = OUT.exists()
    with open(OUT, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not exists:
            w.writeheader()
        w.writerows(new_rows)
    PROGRESS.write_text(json.dumps({"index": start + done}))
    print(f"processed {done} jurisdictions ({start}->{start+done} of {len(juris)}); "
          f"{len(new_rows)} rows appended to {OUT.name}")


if __name__ == "__main__":
    main()
