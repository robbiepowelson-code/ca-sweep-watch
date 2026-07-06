#!/usr/bin/env python3
"""
Generate monthly CPRA request letters for every agency.

Default is DRAFT ONLY — letters are written to outbox/YYYY-MM/ for review.
Sending requires --send plus SMTP settings in config.ini. Nothing is ever
emailed without that explicit flag, so you stay in control of what goes out
under your name.

    python generate_requests.py                # drafts for last calendar month
    python generate_requests.py --send         # actually email (config.ini required)
    python generate_requests.py --agency "City of Fresno"
"""
import argparse
import configparser
import datetime as dt
import smtplib
import sqlite3
from email.message import EmailMessage
from pathlib import Path

from db import connect, ROOT

TEMPLATE = ROOT / "templates" / "cpra_request_template.md"
OUTBOX = ROOT / "outbox"
CONFIG = ROOT / "config.ini"


def last_month() -> tuple[str, str]:
    today = dt.date.today()
    first_this = today.replace(day=1)
    end = first_this - dt.timedelta(days=1)
    start = end.replace(day=1)
    return start.isoformat(), end.isoformat()


def ordinance_clause(con: sqlite3.Connection, agency_id: int) -> str:
    rows = con.execute(
        "SELECT code_section FROM ordinances WHERE agency_id = ? "
        "AND category != 'administrative policy'", (agency_id,)).fetchall()
    if not rows:
        return ""
    secs = ", ".join(r["code_section"] for r in rows)
    return f", including {secs}"


def build_letter(con, agency, cfg, start, end) -> str:
    text = TEMPLATE.read_text(encoding="utf-8")
    subs = {
        "{{agency_name}}": agency["agency_name"],
        "{{requester_name}}": cfg.get("requester", "name", fallback="[NAME]"),
        "{{requester_org}}": cfg.get("requester", "org", fallback=""),
        "{{requester_email}}": cfg.get("requester", "email", fallback="[EMAIL]"),
        "{{requester_mailing_address}}": cfg.get("requester", "mailing_address", fallback=""),
        "{{date}}": dt.date.today().isoformat(),
        "{{period_start}}": start,
        "{{period_end}}": end,
        "{{fee_cap}}": cfg.get("requester", "fee_cap", fallback="25"),
        "{{ordinance_list_clause}}": ordinance_clause(con, agency["id"]),
    }
    for k, v in subs.items():
        text = text.replace(k, v)
    return text


def send_email(cfg, to_addr: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = cfg.get("smtp", "from_addr")
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(cfg.get("smtp", "host"), cfg.getint("smtp", "port", fallback=587)) as s:
        s.starttls()
        s.login(cfg.get("smtp", "user"), cfg.get("smtp", "password"))
        s.send_message(msg)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true", help="email instead of draft")
    ap.add_argument("--agency", help="limit to one agency")
    ap.add_argument("--start"); ap.add_argument("--end")
    args = ap.parse_args()

    start, end = (args.start, args.end) if args.start else last_month()
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG)

    con = connect()
    q = "SELECT * FROM agencies WHERE jurisdiction_type IN ('city','county')"
    params: tuple = ()
    if args.agency:
        q += " AND agency_name = ?"
        params = (args.agency,)
    agencies = con.execute(q, params).fetchall()

    month_dir = OUTBOX / start[:7]
    month_dir.mkdir(parents=True, exist_ok=True)
    drafted = sent = skipped = 0

    for a in agencies:
        letter = build_letter(con, a, cfg, start, end)
        safe = a["agency_name"].replace(" ", "_").replace("/", "-")
        (month_dir / f"{safe}.md").write_text(letter, encoding="utf-8")
        drafted += 1

        sent_date = None
        status = "draft"
        if args.send:
            addr = a["cpra_email"] or a["pd_records_email"]
            if addr:
                send_email(cfg, addr,
                           f"Public Records Act Request — enforcement records {start} to {end}",
                           letter)
                sent_date = dt.date.today().isoformat()
                status = "sent"
                sent += 1
            else:
                skipped += 1  # no email on file; portal/mail needed

        due = ((dt.date.fromisoformat(sent_date) + dt.timedelta(days=10)).isoformat()
               if sent_date else None)
        con.execute(
            """INSERT INTO requests (agency_id, period_start, period_end,
                   sent_date, method, determination_due, status)
               VALUES (?,?,?,?,?,?,?)""",
            (a["id"], start, end, sent_date,
             "email" if sent_date else None, due, status))
    con.commit()
    print(f"period {start}..{end}: {drafted} drafted -> {month_dir}")
    if args.send:
        print(f"{sent} emailed, {skipped} skipped (no address — use portal/mail)")


if __name__ == "__main__":
    main()
