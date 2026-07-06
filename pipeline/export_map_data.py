#!/usr/bin/env python3
"""
Export site/data.json for the public map. Strips everything except what the
public layer needs — no requester info, no file paths, no raw document text.

    python export_map_data.py
"""
import json

from db import connect, ROOT

SITE = ROOT / "site"


def main() -> None:
    con = connect()
    events = [dict(r) for r in con.execute(
        """SELECT agency_name, county, action_type, code_section,
                  action_date, summary, lat, lon, geocode_source, confidence
           FROM v_map_events""")]
    compliance = [dict(r) for r in con.execute(
        """SELECT agency_name, county, jurisdiction_type, lat, lon,
                  requests_sent, produced, overdue, denied
           FROM v_agency_compliance""")]
    ordinances = [dict(r) for r in con.execute(
        """SELECT a.agency_name, a.county, o.code_section, o.ordinance_name,
                  o.category, o.summary, o.status
           FROM ordinances o LEFT JOIN agencies a ON a.id = o.agency_id""")]

    SITE.mkdir(exist_ok=True)
    out = SITE / "data.json"
    out.write_text(json.dumps({
        "generated": __import__("datetime").date.today().isoformat(),
        "events": events,
        "compliance": compliance,
        "ordinances": ordinances,
    }, indent=1), encoding="utf-8")
    print(f"wrote {out}: {len(events)} events, {len(compliance)} agencies, "
          f"{len(ordinances)} ordinances")


if __name__ == "__main__":
    main()
