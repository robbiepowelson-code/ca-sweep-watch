#!/usr/bin/env python3
"""
Build the COMPLETE California jurisdiction list (all 482 incorporated
cities/towns + 58 counties) with coordinates, so the map shows every
jurisdiction — including ones we have no ordinance data for yet.

Sources:
  - US Census 2024 gazetteer (official place list + coordinates)
  - Wikipedia "List of cities and towns in California" (cross-check)
  - Embedded county centroids (58)

Writes data/all_jurisdictions.csv. Runs in GitHub Actions monthly; safe to
re-run anytime. If the network fails, the previous file is kept.

    pip install requests
    python build_full_jurisdictions.py
"""
import csv
import io
import re
import sys
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "all_jurisdictions.csv"
GAZ_URL = ("https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
           "2024_Gazetteer/2024_gaz_place_06.txt")
WIKI_URL = "https://en.wikipedia.org/wiki/List_of_cities_and_towns_in_California"

# All 58 county centroids (approximate geographic centers)
COUNTIES = {
    "Alameda": (37.65, -121.88), "Alpine": (38.60, -119.82),
    "Amador": (38.45, -120.65), "Butte": (39.67, -121.60),
    "Calaveras": (38.20, -120.55), "Colusa": (39.18, -122.24),
    "Contra Costa": (37.92, -121.93), "Del Norte": (41.74, -123.90),
    "El Dorado": (38.78, -120.52), "Fresno": (36.98, -119.65),
    "Glenn": (39.60, -122.39), "Humboldt": (40.70, -123.87),
    "Imperial": (33.04, -115.36), "Inyo": (36.51, -117.41),
    "Kern": (35.34, -118.73), "Kings": (36.08, -119.82),
    "Lake": (39.10, -122.75), "Lassen": (40.67, -120.59),
    "Los Angeles": (34.32, -118.22), "Madera": (37.22, -119.76),
    "Marin": (38.07, -122.74), "Mariposa": (37.57, -119.90),
    "Mendocino": (39.44, -123.39), "Merced": (37.19, -120.72),
    "Modoc": (41.59, -120.72), "Mono": (37.94, -118.89),
    "Monterey": (36.24, -121.31), "Napa": (38.51, -122.33),
    "Nevada": (39.30, -120.77), "Orange": (33.70, -117.76),
    "Placer": (39.06, -120.72), "Plumas": (40.00, -120.84),
    "Riverside": (33.74, -116.00), "Sacramento": (38.45, -121.34),
    "San Benito": (36.61, -121.08), "San Bernardino": (34.84, -116.18),
    "San Diego": (33.03, -116.74), "San Francisco": (37.76, -122.45),
    "San Joaquin": (37.93, -121.27), "San Luis Obispo": (35.39, -120.45),
    "San Mateo": (37.43, -122.33), "Santa Barbara": (34.72, -120.02),
    "Santa Clara": (37.23, -121.70), "Santa Cruz": (37.03, -122.01),
    "Shasta": (40.76, -122.04), "Sierra": (39.58, -120.52),
    "Siskiyou": (41.59, -122.54), "Solano": (38.27, -121.94),
    "Sonoma": (38.53, -122.89), "Stanislaus": (37.56, -120.99),
    "Sutter": (39.03, -121.69), "Tehama": (40.13, -122.24),
    "Trinity": (40.65, -123.11), "Tulare": (36.22, -118.80),
    "Tuolumne": (38.03, -119.95), "Ventura": (34.44, -119.08),
    "Yolo": (38.69, -121.90), "Yuba": (39.27, -121.35),
}


def fetch_gazetteer() -> list[dict]:
    r = requests.get(GAZ_URL, timeout=120)
    r.raise_for_status()
    cities = []
    for row in csv.DictReader(io.StringIO(r.text), delimiter="\t"):
        row = {k.strip(): (v.strip() if v else "") for k, v in row.items()}
        name = row["NAME"]
        if not name.endswith((" city", " town")):
            continue  # skip CDPs (unincorporated — covered by county sheriff)
        cities.append({
            "name": re.sub(r" (city|town)$", "", name),
            "lat": float(row["INTPTLAT"]),
            "lon": float(row["INTPTLONG"]),
        })
    return cities


def wikipedia_names() -> set[str]:
    """City names from Wikipedia's list, for cross-checking."""
    r = requests.get(WIKI_URL, timeout=60,
                     headers={"User-Agent": "ca-sweep-watch/1.0"})
    r.raise_for_status()
    # City rows link like <th scope="row" ...><a ... title="Adelanto, California">
    names = set(re.findall(
        r'title="([^"]+?), California"', r.text))
    # Filter obvious non-cities (counties etc. handled separately)
    return {n for n in names if not n.endswith("County")}


def main() -> None:
    try:
        cities = fetch_gazetteer()
    except Exception as e:
        sys.exit(f"gazetteer fetch failed ({e}); keeping existing {OUT.name}")

    print(f"Census gazetteer: {len(cities)} incorporated cities/towns")
    try:
        wiki = wikipedia_names()
        gaz_names = {c["name"] for c in cities}
        missing_from_gaz = sorted(w for w in wiki if w in gaz_names) and \
            sorted(wiki - gaz_names)[:20]
        missing_from_wiki = sorted(gaz_names - wiki)[:20]
        print(f"Wikipedia cross-check: {len(wiki)} names on Wikipedia list")
        if missing_from_gaz:
            print(f"  on Wikipedia but not gazetteer (check!): {missing_from_gaz}")
        if missing_from_wiki:
            print(f"  in gazetteer but not Wikipedia (check!): {missing_from_wiki}")
    except Exception as e:
        print(f"Wikipedia cross-check skipped ({e})")

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "jurisdiction_type", "lat", "lon", "source"])
        for c in sorted(cities, key=lambda c: c["name"]):
            w.writerow([c["name"], "city", c["lat"], c["lon"], "census_gazetteer_2024"])
        for county, (lat, lon) in sorted(COUNTIES.items()):
            w.writerow([f"{county} County", "county", lat, lon, "county_centroid"])
    print(f"wrote {OUT}: {len(cities)} cities + {len(COUNTIES)} counties")


if __name__ == "__main__":
    main()
