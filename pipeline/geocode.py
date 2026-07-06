#!/usr/bin/env python3
"""
Geocode enforcement_actions rows that have an address but no coordinates,
using the free US Census geocoder (no API key, no usage cap for this scale).

    pip install requests
    python geocode.py
"""
import requests

from db import connect

URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"


def geocode(addr: str, agency: str, county: str):
    q = f"{addr}, {agency.replace('City of ', '')}, CA"
    r = requests.get(URL, params={"address": q, "benchmark": "Public_AR_Current",
                                  "format": "json"}, timeout=30)
    matches = r.json().get("result", {}).get("addressMatches", [])
    if matches:
        c = matches[0]["coordinates"]
        return c["y"], c["x"]
    return None, None


def main() -> None:
    con = connect()
    rows = con.execute(
        """SELECT ea.id, ea.location_text, a.agency_name, a.county
           FROM enforcement_actions ea JOIN agencies a ON a.id = ea.agency_id
           WHERE ea.lat IS NULL AND ea.location_text IS NOT NULL""").fetchall()
    done = 0
    for r in rows:
        lat, lon = geocode(r["location_text"], r["agency_name"], r["county"])
        if lat:
            con.execute(
                """UPDATE enforcement_actions SET lat=?, lon=?,
                       geocode_source='geocoded_address' WHERE id=?""",
                (lat, lon, r["id"]))
            done += 1
    con.commit()
    print(f"geocoded {done}/{len(rows)} addresses")


if __name__ == "__main__":
    main()
