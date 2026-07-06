#!/usr/bin/env python3
"""
Ingest documents produced by agencies.

Drop received files into inbox/<Agency_Name>/ then run:
    pip install pdfplumber Pillow
    python ingest.py

For each file it: hashes + registers it, extracts text (PDF) or EXIF GPS
(images), scans text for enforcement events (code sections, dates,
locations, GPS coordinates), and writes enforcement_actions rows.
Optionally set ANTHROPIC_API_KEY and pass --llm to get per-document
summaries via the Claude API.
"""
import argparse
import datetime as dt
import hashlib
import os
import re
from pathlib import Path

from db import connect, ROOT

INBOX = ROOT / "inbox"

CODE_PAT = re.compile(
    r"(647\s*\(?e\)?|602(?:\.\d+)?|41\.18|56\.11|12\.52[\.\d]*|63\.0102"
    r"|\b\d{1,2}\.\d{2,4}(?:\.\d{2,4})?\b(?=[^%]*(?:camp|lodg|sleep|sit|lie|encamp)))",
    re.I)
ACTION_PAT = re.compile(
    r"\b(sweep|encampment (?:removal|resolution|closure|abatement)|clean[- ]?up"
    r"|citation|cited|arrest(?:ed)?|notice to vacate|property (?:removal|stored|discarded))\b",
    re.I)
DATE_PAT = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b")
GPS_TEXT_PAT = re.compile(
    r"(-?\d{2}\.\d{3,})[,\s]+(-?1\d{2}\.\d{3,})")  # e.g. 34.0522, -118.2437
ADDR_PAT = re.compile(
    r"\b\d{2,5}\s+[A-Z][A-Za-z]+(?:\s[A-Z][A-Za-z]+){0,3}\s"
    r"(?:St|Ave|Blvd|Rd|Dr|Way|Hwy|Pkwy|Ln|Ct)\b")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pdf_text(path: Path) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception as e:
        return f""  # scanned PDF -> needs OCR pass (see README: ocrmypdf)


def exif_gps(path: Path):
    """Return (lat, lon, timestamp) from image EXIF, or (None, None, None)."""
    try:
        from PIL import Image
        from PIL.ExifTags import GPSTAGS, TAGS
        img = Image.open(path)
        raw = img._getexif() or {}
        tags = {TAGS.get(k, k): v for k, v in raw.items()}
        ts = tags.get("DateTimeOriginal") or tags.get("DateTime")
        gps_raw = tags.get("GPSInfo")
        if not gps_raw:
            return None, None, ts
        gps = {GPSTAGS.get(k, k): v for k, v in gps_raw.items()}

        def to_deg(vals, ref):
            d = float(vals[0]) + float(vals[1]) / 60 + float(vals[2]) / 3600
            return -d if ref in ("S", "W") else d

        lat = to_deg(gps["GPSLatitude"], gps.get("GPSLatitudeRef", "N"))
        lon = to_deg(gps["GPSLongitude"], gps.get("GPSLongitudeRef", "E"))
        return lat, lon, ts
    except Exception:
        return None, None, None


def llm_summary(text: str) -> str:
    """Optional Claude API summarization of a document's enforcement content."""
    import anthropic
    client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY
    msg = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=400,
        messages=[{"role": "user", "content":
            "Summarize the encampment-enforcement content of this public "
            "record in 3 sentences: what happened, where, when, under what "
            "code section, and how many people/property items were affected. "
            "If none, say 'no enforcement content'.\n\n" + text[:15000]}])
    return msg.content[0].text


def extract_actions(text: str):
    """Yield rough enforcement-event dicts from document text."""
    for m in ACTION_PAT.finditer(text):
        window = text[max(0, m.start() - 300): m.end() + 300]
        gps = GPS_TEXT_PAT.search(window)
        # search for code sections with coordinates removed, so a latitude
        # like 36.7378 is never mistaken for an ordinance number
        code = CODE_PAT.search(GPS_TEXT_PAT.sub(" ", window))
        date = DATE_PAT.search(window)
        addr = ADDR_PAT.search(window)
        yield {
            "action_type": m.group(1).lower(),
            "code_section": code.group(0) if code else None,
            "action_date": date.group(0) if date else None,
            "lat": float(gps.group(1)) if gps else None,
            "lon": float(gps.group(2)) if gps else None,
            "location_text": addr.group(0) if addr else None,
            "geocode_source": "report_text" if gps else
                              ("geocoded_address" if addr else None),
            "summary": window.replace("\n", " ").strip()[:400],
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true",
                    help="summarize each document with the Claude API")
    args = ap.parse_args()

    con = connect()
    INBOX.mkdir(exist_ok=True)
    new_docs = actions = 0

    for agency_dir in sorted(p for p in INBOX.iterdir() if p.is_dir()):
        name = agency_dir.name.replace("_", " ")
        row = con.execute("SELECT id FROM agencies WHERE agency_name = ?",
                          (name,)).fetchone()
        agency_id = row["id"] if row else None

        for f in sorted(agency_dir.rglob("*")):
            if not f.is_file():
                continue
            if con.execute("SELECT 1 FROM documents WHERE file_path = ?",
                           (str(f),)).fetchone():
                continue
            ext = f.suffix.lower()
            text, lat, lon, ts = "", None, None, None
            if ext == ".pdf":
                text = pdf_text(f)
            elif ext in (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic"):
                lat, lon, ts = exif_gps(f)
            elif ext in (".txt", ".csv"):
                text = f.read_text(errors="ignore")

            summary = None
            if args.llm and text.strip():
                try:
                    summary = llm_summary(text)
                except Exception as e:
                    summary = f"[llm failed: {e}]"

            cur = con.execute(
                """INSERT INTO documents (agency_id, file_path, sha256,
                       file_type, received_date, extracted_text,
                       exif_lat, exif_lon, exif_timestamp, summary, processed)
                   VALUES (?,?,?,?,?,?,?,?,?,?,1)""",
                (agency_id, str(f), sha256(f), ext.lstrip("."),
                 dt.date.today().isoformat(), text[:200000],
                 lat, lon, ts, summary))
            doc_id = cur.lastrowid
            new_docs += 1

            # image with GPS = a locatable enforcement/sweep photo
            if lat is not None:
                con.execute(
                    """INSERT INTO enforcement_actions
                       (agency_id, document_id, action_type, action_date,
                        lat, lon, geocode_source, summary, confidence)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (agency_id, doc_id, "sweep_photo", ts, lat, lon,
                     "exif", f"Geotagged photo: {f.name}", "high"))
                actions += 1

            for ev in extract_actions(text):
                con.execute(
                    """INSERT INTO enforcement_actions
                       (agency_id, document_id, action_type, code_section,
                        action_date, location_text, lat, lon, geocode_source,
                        summary, confidence)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (agency_id, doc_id, ev["action_type"], ev["code_section"],
                     ev["action_date"], ev["location_text"], ev["lat"],
                     ev["lon"], ev["geocode_source"], ev["summary"], "medium"))
                actions += 1

    con.commit()
    print(f"ingested {new_docs} documents, extracted {actions} candidate actions")
    print("addresses without coordinates: run geocode.py (Census geocoder, free)")


if __name__ == "__main__":
    main()
