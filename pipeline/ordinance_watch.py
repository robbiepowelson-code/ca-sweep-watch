#!/usr/bin/env python3
"""
Ordinance change watcher.

Takes a snapshot of the current ordinance dataset and diffs it against the
previous snapshot, so every monthly run answers: which jurisdictions ADDED,
CHANGED, or REMOVED anti-camping laws since last month?

    python ordinance_watch.py            # diff current data vs last snapshot
    python ordinance_watch.py --refetch  # first re-download the Berkeley
                                         # sheet (requires internet), then diff

Outputs:
    data/ordinance_snapshots/YYYY-MM-DD.csv   (immutable history)
    data/ordinance_changes.csv                (append-only change log,
                                               shown on the map site)
"""
import argparse
import csv
import datetime as dt
import hashlib
import subprocess
import sys
from pathlib import Path

from berkeley_common import parse_appendix, DATA

SNAP_DIR = DATA / "ordinance_snapshots"
CHANGES = DATA / "ordinance_changes.csv"
FIELDS = ["county", "jurisdiction", "category", "cite", "text"]


def current_rows() -> dict[str, dict]:
    """Key each law row by jurisdiction+cite (or text hash when no cite)."""
    rows = {}
    for r in parse_appendix():
        if "Ordinance" not in r["category"] and r["category"] != "Policy Change":
            continue
        suffix = r["cite"] or hashlib.sha1(r["text"].encode()).hexdigest()[:10]
        key = f"{r['jurisdiction']}|{suffix}"
        rows[key] = {k: r[k] for k in FIELDS}
    return rows


def load_snapshot(path: Path) -> dict[str, dict]:
    rows = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = r.pop("key")
            rows[key] = r
    return rows


def save_snapshot(rows: dict[str, dict], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["key"] + FIELDS)
        w.writeheader()
        for key, r in sorted(rows.items()):
            w.writerow({"key": key, **r})


def append_changes(changes: list[dict]) -> None:
    exists = CHANGES.exists()
    with open(CHANGES, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date", "jurisdiction", "change_type", "detail"])
        if not exists:
            w.writeheader()
        w.writerows(changes)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refetch", action="store_true",
                    help="re-download the Berkeley appendix before diffing")
    args = ap.parse_args()

    if args.refetch:
        subprocess.run([sys.executable,
                        Path(__file__).parent / "fetch_berkeley_appendix.py"],
                       check=False)

    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    now = current_rows()

    prior_snaps = sorted(SNAP_DIR.glob("*.csv"))
    if not prior_snaps:
        save_snapshot(now, SNAP_DIR / f"{today}.csv")
        print(f"Baseline snapshot saved: {len(now)} law records. "
              "Run again after future data updates to see diffs.")
        return

    prev = load_snapshot(prior_snaps[-1])
    changes = []
    for key, r in now.items():
        if key not in prev:
            changes.append({"date": today, "jurisdiction": r["jurisdiction"],
                            "change_type": "added",
                            "detail": f"{r['category']}: {r['cite'] or r['text'][:120]}"})
        elif r["text"] != prev[key]["text"] or r["category"] != prev[key]["category"]:
            changes.append({"date": today, "jurisdiction": r["jurisdiction"],
                            "change_type": "modified",
                            "detail": f"{r['cite'] or key}: text/category updated"})
    for key, r in prev.items():
        if key not in now:
            changes.append({"date": today, "jurisdiction": r["jurisdiction"],
                            "change_type": "removed",
                            "detail": f"{r['category']}: {r['cite'] or r['text'][:120]}"})

    save_snapshot(now, SNAP_DIR / f"{today}.csv")
    if changes:
        append_changes(changes)
        print(f"{len(changes)} changes since {prior_snaps[-1].stem}:")
        for c in changes[:20]:
            print(f"  [{c['change_type']}] {c['jurisdiction']}: {c['detail'][:90]}")
    else:
        print(f"No ordinance changes since {prior_snaps[-1].stem}.")


if __name__ == "__main__":
    main()
