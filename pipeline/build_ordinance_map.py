#!/usr/bin/env python3
"""
Build site/ordinances.json: one map dot for EVERY California jurisdiction.

- Jurisdictions in the ordinance dataset get status enacted / proposed /
  policy_change and their laws in the popup.
- All remaining cities/counties (from data/all_jurisdictions.csv, built by
  build_full_jurisdictions.py from the Census gazetteer) get status
  "no_data" — a gray dot meaning "no ordinance information collected yet",
  which is not the same as "no ordinance exists".

    python build_ordinance_map.py
"""
import csv
import json
import unicodedata
from collections import defaultdict
from pathlib import Path

from berkeley_common import parse_appendix, load_coords, DATA

SITE = Path(__file__).resolve().parent.parent / "site"
ALL_J = DATA / "all_jurisdictions.csv"
ORD_CATS = ("Past Ordinance", "Proposed Ordinance", "Policy Change")

# dataset/display name -> census gazetteer name
ALIASES = {
    "ventura": "san buenaventura (ventura)",
    "san buenaventura": "san buenaventura (ventura)",
}


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = s.lower().strip()
    return ALIASES.get(s, s)


def main() -> None:
    coords = load_coords()

    # group dataset laws by jurisdiction
    groups = defaultdict(list)
    for row in parse_appendix():
        if not any(c in row["category"] for c in ORD_CATS):
            continue
        jtype = "county" if row["is_county_level"] else "city"
        groups[(row["jurisdiction"], jtype, row["county"])].append(row)

    dots, seen, missing = [], set(), []
    for (jur, jtype, county), entries in sorted(groups.items()):
        c = coords.get((jur, jtype))
        if not c:
            missing.append(f"{jur} ({jtype})")
            continue
        has_enacted = any("Past Ordinance" in e["category"] for e in entries)
        has_proposed = any("Proposed" in e["category"] for e in entries)
        seen.add((norm(c["display_name"]), jtype))
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

    # add every remaining CA jurisdiction as a gray "no data yet" dot
    def county_token(name: str) -> str:
        """'San Francisco (City & County)' / 'Kern County' -> base county name"""
        return (norm(name).replace(" (city & county)", "")
                .replace("city and county of ", "").replace(" county", "").strip())

    covered_counties = {county_token(d["name"]) for d in dots if d["type"] == "county"}
    added_nodata = 0
    if ALL_J.exists():
        with open(ALL_J, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                jtype = row["jurisdiction_type"]
                if jtype == "county":
                    tok = county_token(row["name"])
                    if tok in covered_counties:
                        continue
                    # consolidated city-county: SF city data covers the county
                    if tok == "san francisco" and ("san francisco", "city") in seen:
                        continue
                elif (norm(row["name"]), "city") in seen:
                    continue
                dots.append({
                    "name": row["name"], "type": jtype, "county": "",
                    "lat": float(row["lat"]), "lon": float(row["lon"]),
                    "status": "no_data", "laws": [],
                })
                added_nodata += 1
    else:
        print(f"note: {ALL_J.name} not found — run build_full_jurisdictions.py "
              "to add gray dots for every remaining CA jurisdiction")

    changes = []
    changes_csv = DATA / "ordinance_changes.csv"
    if changes_csv.exists():
        with open(changes_csv, newline="", encoding="utf-8") as f:
            changes = list(csv.DictReader(f))[-50:]

    SITE.mkdir(exist_ok=True)
    out = SITE / "ordinances.json"
    out.write_text(json.dumps({
        "generated": __import__("datetime").date.today().isoformat(),
        "source": "UC Berkeley Law HSP appendix (SSRN 5257640) + Census gazetteer",
        "jurisdictions": dots,
        "recent_changes": changes,
    }, indent=1), encoding="utf-8")
    print(f"wrote {out}: {len(dots)} dots "
          f"({len(dots) - added_nodata} with law data, {added_nodata} no-data)")
    if missing:
        print(f"NO COORDS for {len(missing)}: {missing}")


if __name__ == "__main__":
    main()
