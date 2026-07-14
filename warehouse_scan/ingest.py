"""Scan-record ingest: JSONL replay -> SQLite store, with placard location tagging.

Phase 1 of docs/WMS-INTEGRATION.md. Accepts the JSONL files the decoder already
writes (results/stream.jsonl, results/scan.jsonl) and normalizes them into an
append-only `scans` table.

Location tagging: a decoded value starting with "LOC:" is a rack placard, not
inventory. Placards set the "current location context"; subsequent inventory
reads inherit that location. When both records carry parseable timestamps the
context expires after `placard_window_s` seconds; records without timestamps
fall back to file order, which matches how the stream decoder writes them.

Ingest is idempotent: each record gets a deterministic scan_id, so replaying
the same file never duplicates rows.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

LOC_PREFIX = "LOC:"
DEFAULT_DB = Path("results") / "scans.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
  scan_id    TEXT PRIMARY KEY,
  mission_id TEXT NOT NULL,
  ts         TEXT,
  barcode    TEXT NOT NULL,
  symbology  TEXT,
  is_placard INTEGER NOT NULL DEFAULT 0,
  location   TEXT,
  loc_source TEXT,
  raw        TEXT
);
CREATE INDEX IF NOT EXISTS idx_scans_mission ON scans(mission_id);
CREATE INDEX IF NOT EXISTS idx_scans_barcode ON scans(barcode);
"""


def connect(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    return conn


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _scan_id(mission_id: str, rec: dict, barcode: str) -> str:
    if rec.get("scan_id"):
        return str(rec["scan_id"])
    key = f"{mission_id}|{rec.get('ts', '')}|{barcode}|{rec.get('source', '')}"
    return hashlib.sha1(key.encode()).hexdigest()


def ingest_jsonl(
    conn: sqlite3.Connection,
    jsonl_path: str | Path,
    mission_id: str = "default",
    placard_window_s: float = 10.0,
) -> dict:
    """Replay one JSONL file into the store. Returns a summary dict."""
    inserted = skipped = placards = tagged = bad = 0
    current_loc: str | None = None
    current_loc_ts: datetime | None = None

    with Path(jsonl_path).open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            barcode = rec.get("barcode") or rec.get("data")
            if barcode is None or barcode == "":
                bad += 1
                continue
            barcode = str(barcode)  # tolerate numeric EANs from other emitters
            ts = _parse_ts(rec.get("ts"))
            is_placard = barcode.startswith(LOC_PREFIX)

            if is_placard:
                location = barcode[len(LOC_PREFIX):]
                loc_source = "placard"
                current_loc, current_loc_ts = location, ts
                placards += 1
            else:
                location, loc_source = None, None
                if current_loc is not None:
                    in_window = True
                    if ts is not None and current_loc_ts is not None:
                        in_window = (
                            0 <= (ts - current_loc_ts).total_seconds() <= placard_window_s
                        )
                    if in_window:
                        location, loc_source = current_loc, "placard-context"
                        tagged += 1

            cur = conn.execute(
                "INSERT OR IGNORE INTO scans "
                "(scan_id, mission_id, ts, barcode, symbology, is_placard,"
                " location, loc_source, raw) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    _scan_id(mission_id, rec, barcode),
                    mission_id,
                    rec.get("ts"),
                    barcode,
                    rec.get("symbology"),
                    1 if is_placard else 0,
                    location,
                    loc_source,
                    json.dumps(rec),
                ),
            )
            if cur.rowcount:
                inserted += 1
            else:
                skipped += 1
    conn.commit()
    return {
        "inserted": inserted,
        "skipped_duplicates": skipped,
        "placards": placards,
        "location_tagged": tagged,
        "bad_lines": bad,
    }


def missions(conn: sqlite3.Connection) -> list[dict]:
    """All missions in the store: name, scan/placard counts, time range."""
    rows = conn.execute(
        "SELECT mission_id, COUNT(*), SUM(is_placard), MIN(ts), MAX(ts) "
        "FROM scans GROUP BY mission_id ORDER BY MAX(ts) DESC"
    ).fetchall()
    return [
        {"mission_id": m, "scans": n, "placards": p or 0,
         "first_ts": t0, "last_ts": t1}
        for m, n, p, t0, t1 in rows
    ]


def clear_mission(conn: sqlite3.Connection, mission_id: str) -> int:
    """Delete all scans for a mission (for re-running a test under the same
    name). Returns the number of rows removed. Missions are point-in-time
    snapshots — re-ingesting a new session into an old mission silently blends
    evidence across runs (inflated sightings, stale matches/visits)."""
    cur = conn.execute("DELETE FROM scans WHERE mission_id = ?", (mission_id,))
    conn.commit()
    return cur.rowcount


def observations(conn: sqlite3.Connection, mission_id: str | None = None) -> list[dict]:
    """Deduped inventory observations: one row per (barcode, location)."""
    where = "WHERE is_placard = 0"
    args: tuple = ()
    if mission_id:
        where += " AND mission_id = ?"
        args = (mission_id,)
    rows = conn.execute(
        f"SELECT barcode, location, COUNT(*), MIN(ts), MAX(ts), "
        f"GROUP_CONCAT(DISTINCT symbology) "
        f"FROM scans {where} GROUP BY barcode, location",
        args,
    ).fetchall()
    return [
        {"barcode": b, "location": loc, "sightings": n, "first_ts": t0,
         "last_ts": t1, "symbologies": set((syms or "").split(",")) - {""}}
        for b, loc, n, t0, t1, syms in rows
    ]


def visited_locations(conn: sqlite3.Connection, mission_id: str | None = None) -> set[str]:
    """Locations where at least one ITEM read was location-tagged.

    Deliberately excludes placard-only sightings: placards are large QRs
    readable from transit range, while item labels need close approach — a
    placard glimpse alone is not evidence the shelf faces were inspected, so
    it must not enable 'missing' claims (see reconcile.py).
    """
    where = "WHERE is_placard = 0 AND location IS NOT NULL"
    args: tuple = ()
    if mission_id:
        where += " AND mission_id = ?"
        args = (mission_id,)
    rows = conn.execute(f"SELECT DISTINCT location FROM scans {where}", args).fetchall()
    return {r[0] for r in rows}


def placard_locations(conn: sqlite3.Connection, mission_id: str | None = None) -> set[str]:
    """Locations whose placard was seen (regardless of item reads there)."""
    where = "WHERE is_placard = 1 AND location IS NOT NULL"
    args: tuple = ()
    if mission_id:
        where += " AND mission_id = ?"
        args = (mission_id,)
    rows = conn.execute(f"SELECT DISTINCT location FROM scans {where}", args).fetchall()
    return {r[0] for r in rows}
