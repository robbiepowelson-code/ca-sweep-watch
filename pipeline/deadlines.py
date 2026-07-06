#!/usr/bin/env python3
"""
CPRA deadline tracker.

    python deadlines.py               # mark overdue, list them
    python deadlines.py --letters     # also generate escalation letters
                                      #   -> outbox/escalations/

Gov. Code § 7922.535: determination due 10 days after receipt; one 14-day
extension allowed with written notice ("unusual circumstances").
"""
import argparse
import configparser
import datetime as dt
from pathlib import Path

from db import connect, ROOT

TEMPLATE = ROOT / "templates" / "cpra_followup_nonresponse.md"
OUT = ROOT / "outbox" / "escalations"
CONFIG = ROOT / "config.ini"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--letters", action="store_true")
    args = ap.parse_args()

    cfg = configparser.ConfigParser()
    cfg.read(CONFIG)
    con = connect()
    today = dt.date.today().isoformat()

    con.execute(
        """UPDATE requests SET status = 'overdue'
           WHERE status IN ('sent','acknowledged','extended')
             AND COALESCE(extended_due, determination_due) < ?""", (today,))
    con.commit()

    rows = con.execute(
        """SELECT r.id, r.sent_date, r.determination_due, a.agency_name
           FROM requests r JOIN agencies a ON a.id = r.agency_id
           WHERE r.status = 'overdue' ORDER BY r.sent_date""").fetchall()

    if not rows:
        print("No overdue requests.")
        return
    print(f"{len(rows)} OVERDUE requests:")
    for r in rows:
        days = (dt.date.today() - dt.date.fromisoformat(r["sent_date"])).days
        print(f"  #{r['id']} {r['agency_name']} — sent {r['sent_date']} ({days} days ago)")

    if args.letters:
        OUT.mkdir(parents=True, exist_ok=True)
        tmpl = TEMPLATE.read_text(encoding="utf-8")
        for r in rows:
            days = (dt.date.today() - dt.date.fromisoformat(r["sent_date"])).days
            letter = (tmpl
                .replace("{{agency_name}}", r["agency_name"])
                .replace("{{requester_name}}", cfg.get("requester", "name", fallback="[NAME]"))
                .replace("{{requester_org}}", cfg.get("requester", "org", fallback=""))
                .replace("{{requester_email}}", cfg.get("requester", "email", fallback="[EMAIL]"))
                .replace("{{date}}", today)
                .replace("{{original_request_date}}", r["sent_date"])
                .replace("{{days_elapsed}}", str(days)))
            safe = r["agency_name"].replace(" ", "_").replace("/", "-")
            (OUT / f"{safe}_{today}.md").write_text(letter, encoding="utf-8")
            con.execute(
                """INSERT INTO request_events (request_id, event_date,
                       event_type, detail) VALUES (?,?,?,?)""",
                (r["id"], today, "escalation", "non-response letter generated"))
            con.execute("UPDATE requests SET status='escalated' WHERE id=?",
                        (r["id"],))
        con.commit()
        print(f"Escalation letters written to {OUT}")


if __name__ == "__main__":
    main()
