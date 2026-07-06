#!/usr/bin/env python3
"""Shared DB helpers. Creates sweepwatch.db from schema.sql and loads CSVs."""
import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "sweepwatch.db"
SCHEMA = Path(__file__).resolve().parent / "schema.sql"
DATA = ROOT / "data"


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA.read_text())
    return con


def load_agencies(con: sqlite3.Connection) -> int:
    n = 0
    with open(DATA / "agencies.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            con.execute(
                """INSERT INTO agencies (agency_name, jurisdiction_type, county,
                       cpra_email, cpra_portal_url, pd_records_email, notes)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(agency_name) DO UPDATE SET
                       cpra_email=excluded.cpra_email,
                       cpra_portal_url=excluded.cpra_portal_url,
                       pd_records_email=excluded.pd_records_email""",
                (row["agency_name"], row["jurisdiction_type"], row["county"],
                 row["cpra_email"], row["cpra_portal_url"],
                 row["pd_records_email"], row.get("notes", "")),
            )
            n += 1
    con.commit()
    return n


def load_ordinances(con: sqlite3.Connection) -> int:
    n = 0
    with open(DATA / "ordinances.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            j = row["jurisdiction"]
            name = j if j == "California" else (
                j if j.startswith(("City of", "County")) else
                (f"{j} County" if row["jurisdiction_type"] == "county"
                 else f"City of {j}")
            )
            cur = con.execute(
                "SELECT id FROM agencies WHERE agency_name = ? OR agency_name = ?",
                (name, j))
            hit = cur.fetchone()
            agency_id = hit["id"] if hit else None
            con.execute(
                """INSERT OR IGNORE INTO ordinances
                   (agency_id, code_section, ordinance_name, category, summary,
                    status, date_enacted, penalty, source, verification_status)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (agency_id, row["code_section"], row["ordinance_name"],
                 row["category"], row["summary"], row["status"],
                 row["date_enacted_or_amended"], row["penalty"],
                 row["source"], row["verification_status"]),
            )
            n += 1
    con.commit()
    return n


if __name__ == "__main__":
    con = connect()
    print(f"agencies loaded: {load_agencies(con)}")
    print(f"ordinances loaded: {load_ordinances(con)}")
    print(f"db: {DB_PATH}")
