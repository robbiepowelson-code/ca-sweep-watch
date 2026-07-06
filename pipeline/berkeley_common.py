"""Shared parsing of the Berkeley HSP appendix CSV into per-jurisdiction records."""
import csv
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

CITE_PATTERNS = [
    r"[A-Z][A-Za-z .]+,\s*Cal\.?,?\s*(?:Mun\.\s*)?Code\s*§§?\s*[\d.\-()A-Za-z]+(?:,\s*[\d.\-()]+)*\s*(?:\(\d{4}\))?",
    r"Municipal [Cc]ode\s*§?\s*[\d][\d.\-]+",
    r"§§?\s*[\d][\d.\-()]*(?:,\s*[\d][\d.\-()]*)*",
    r"Section[s]?\s+[\d][\d.\-()]+",
    r"Sec\.\s*[\d][\d.\-()]+",
    r"Chapter\s+[\d][\d.]*",
    r"Ordinance\s+(?:[Nn]o\.\s*)?[\d]{3,4}\b",
    r"codes?\s+[\d]+\.[\d]+(?:-[\d.]+)?",
    r"\b\d{1,2}\.\d{2,3}\.\d{2,4}(?:\s*[-–]\s*\d[\d.]*)?\b",
    r"\b\d{1,2}\.\d{2,3}(?:\s*[-–]\s*\d{1,2}\.\d{2,3})\b",
]
CITE = re.compile("|".join(f"({p})" for p in CITE_PATTERNS))


def parse_appendix(path=None):
    """Yield dicts: county, jurisdiction, category, cite, text for every row."""
    path = path or DATA / "berkeley_hsp_appendix_raw.csv"
    raw = list(csv.reader(open(path, encoding="utf-8")))[1:]
    county = ""
    for r in raw:
        r = (r + [""] * 7)[:7]
        if r[0].strip():
            county = r[0].strip()
        city = r[4].strip().lstrip("†").strip()
        cat = r[5].strip()
        text = r[6].strip()
        if not text:
            continue
        m = CITE.search(text)
        yield {
            "county": county,
            "jurisdiction": city or county,
            "is_county_level": not city,
            "category": cat,
            "cite": re.sub(r"\s+", " ", m.group(0)).strip(" ,.") if m else "",
            "text": text,
        }


def load_coords():
    """jurisdiction (as in dataset) -> dict with display_name, type, lat, lon."""
    coords = {}
    with open(DATA / "jurisdiction_coords.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row["jurisdiction"], row["jurisdiction_type"])
            coords[key] = {
                "display_name": row["display_name"],
                "jurisdiction_type": row["jurisdiction_type"],
                "lat": float(row["lat"]), "lon": float(row["lon"]),
                "source": row["source"],
            }
    return coords
