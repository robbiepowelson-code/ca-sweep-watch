#!/usr/bin/env python3
"""
Build site/ordinances.json: one map dot per jurisdiction with its
anti-camping laws, categorized (enacted / proposed / policy change), plus
recent changes from data/ordinance_changes.csv if present.

    python build_ordinance_map.py
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

from berkeley_common import parse_appendix, load_coords, DATA

SITE = Path(__file__).resolve().parent.parent / "site"

ORD_CATS = ("Past Ordinance", "Proposed Ordinance", "Policy Change")


def main() -> None:
    coords = load_coords()
    groups = defaultdict(list)
    for row in parse_appendix():
        if not any(c in row["category"] for c in ORD_CATS):
            continue  # skip pure anecdotes/statistics on the law layer
        jtype = "county" if row["is_county_level"] else "city"
        groups[(row["jurisdiction"], jtype, row["county"])].append(row)

    dots, missing = [], []
    for (jur, jtype, county), entries in sorted(groups.items()):
        c = coords.get((jur, jtype))
        if not c:
            missing.append(f"{jur} ({jtype})")
            continue
        has_enacted = any("Past Ordinance" in e["category"] for e in entries)
        has_proposed = any("Proposed" in e["category"] for e in entries)
        dots.append({
            "name": c["display_name"],
            "type": jtype,
            "county": county.replace(" County", ""),
            "lat": c["lat"], "lon": c["lon"],
            "status": ("enacted" if has_enacted else
                       "proposed" if has_proposed else "policy_change"),
            "laws": [{
                "category": e["category"],
                "cite": e["cite"],
                "summary": e["text"][:400],
            } for e in entries],
        })

    changes = []
    changes_csv = DATA / "ordinance_changes.csv"
    if changes_csv.exists():
        with open(changes_csv, newline="", encoding="utf-8") as f:
            changes = list(csv.DictReader(f))[-50:]  # latest 50

    SITE.mkdir(exist_ok=True)
    out = SITE / "ordinances.json"
    out.write_text(json.dumps({
        "generated": __import__("datetime").date.today().isoformat(),
        "source": "UC Berkeley Law HSP appendix (SSRN 5257640) + local additions",
        "jurisdictions": dots,
        "recent_changes": changes,
    }, indent=1), encoding="utf-8")
    print(f"wrote {out}: {len(dots)} jurisdiction dots, "
          f"{len(changes)} recent changes")
    if missing:
        print(f"NO COORDS for {len(missing)}: {missing}")


if __name__ == "__main__":
    main()
