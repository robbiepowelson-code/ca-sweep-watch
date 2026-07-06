#!/usr/bin/env python3
"""
Fetch the UC Berkeley Homelessness Service Project appendix
("The State of Homelessness Criminalization in California After Grants Pass
v. Johnson", SSRN 5257640) from its public Google Sheet and save every tab
as CSV under data/berkeley_appendix/.

Run on your own machine with internet:
    pip install requests
    python fetch_berkeley_appendix.py
"""
import csv
import io
import re
import sys
from pathlib import Path

import requests

SHEET_ID = "1HNo5liFOx88Yf0KEd0UN7dzwonL7axbHjiBgezm6MUQ"
KNOWN_GIDS = ["14190262"]  # tab linked from law.berkeley.edu article
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "berkeley_appendix"


def discover_gids() -> list[str]:
    """Scrape the sheet's HTML view for all tab gids."""
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/htmlview"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    gids = sorted(set(re.findall(r'gid[=:]"?(\d+)', r.text)))
    return gids or KNOWN_GIDS


def fetch_tab(gid: str) -> str | None:
    url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
        f"/export?format=csv&gid={gid}"
    )
    r = requests.get(url, timeout=120)
    if r.status_code != 200 or r.text.lstrip().startswith("<"):
        return None
    return r.text


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gids = discover_gids()
    print(f"Found {len(gids)} candidate tabs: {gids}")
    saved = 0
    for gid in gids:
        text = fetch_tab(gid)
        if not text:
            print(f"  gid {gid}: skipped (not exportable)")
            continue
        # Use first header cell to make a readable filename
        first_row = next(csv.reader(io.StringIO(text)), ["tab"])
        label = re.sub(r"\W+", "_", (first_row[0] or "tab"))[:40] or "tab"
        path = OUT_DIR / f"gid_{gid}_{label}.csv"
        path.write_text(text, encoding="utf-8")
        print(f"  gid {gid}: saved {path.name} ({len(text)} bytes)")
        saved += 1
    if not saved:
        sys.exit("No tabs saved — check sharing settings or connectivity.")
    print(f"Done. Next: python merge_berkeley.py to fold into ordinances.csv")


if __name__ == "__main__":
    main()
