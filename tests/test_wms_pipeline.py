"""End-to-end test of the WMS pipeline: JSONL scans -> ingest -> reconcile.

Runs with plain python (python tests/test_wms_pipeline.py) or pytest.
Covers every verdict type, ingest idempotency, the placard time window,
placard-only bays (must be `unverified`, never `missing`), no-location-context
evidence notes, numeric barcode tolerance, and BOM'd expected CSVs.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from warehouse_scan.ingest import (
    connect,
    ingest_jsonl,
    observations,
    placard_locations,
    visited_locations,
)
from warehouse_scan.reconcile import Verdict, reconcile, summarize
from warehouse_scan.wms import FileExchangeAdapter

STREAM = [
    # bay 1: placard then its expected item
    {"data": "LOC:A07-B12-L3", "symbology": "QRCODE", "ts": "2026-07-14T10:00:00+00:00", "source": "s#1"},
    {"data": "SKU-000123-A", "symbology": "CODE128", "ts": "2026-07-14T10:00:04+00:00", "source": "s#2"},
    # bay 2: placard, a misplaced known item, an unknown item (read twice,
    # once as a JSON number — must be tolerated and counted as a 2nd sighting)
    {"data": "LOC:A07-B13-L1", "symbology": "QRCODE", "ts": "2026-07-14T10:01:00+00:00", "source": "s#3"},
    {"data": "TOOL-777", "symbology": "CODE128", "ts": "2026-07-14T10:01:03+00:00", "source": "s#4"},
    {"data": "4006381333931", "symbology": "EAN13", "ts": "2026-07-14T10:01:05+00:00", "source": "s#5"},
    {"data": 4006381333931, "symbology": "EAN13", "ts": "2026-07-14T10:01:06+00:00", "source": "s#5b"},
    # a one-off corrupted read (phantom) — the sightings threshold must catch it
    {"data": "PHANT0M-1", "symbology": "CODE128", "ts": "2026-07-14T10:01:07+00:00", "source": "s#5c"},
    # a single-sighting QR — RS-corrected, so it must BYPASS the threshold
    {"data": "QR-ONLY-1", "symbology": "QRCODE", "ts": "2026-07-14T10:01:08+00:00", "source": "s#5d"},
    # bay 3: placard seen in transit, NO item reads -> must never yield 'missing'
    {"data": "LOC:A08-B01-L1", "symbology": "QRCODE", "ts": "2026-07-14T10:02:00+00:00", "source": "s#6"},
    # a known item read far outside any placard window -> no location context
    {"data": "STALE-1", "symbology": "CODE128", "ts": "2026-07-14T10:05:00+00:00", "source": "s#7"},
]

EXPECTED_CSV = """location,barcode,description
A07-B12-L3,SKU-000123-A,widget case
A07-B13-L1,WIDGET-999,missing widget
A07-B13-L1,STALE-1,item read without context
A09-B01-L1,GADGET-1,never visited
A07-B14-L2,TOOL-777,tool expected elsewhere
A08-B01-L1,EMPTY-BAY-ITEM,placard-only bay
"""


def _by_verdict(verdicts: list[Verdict], kind: str) -> list[Verdict]:
    return [v for v in verdicts if v.verdict == kind]


def test_pipeline() -> None:
    tmp = Path(tempfile.mkdtemp())
    jsonl = tmp / "stream.jsonl"
    jsonl.write_text("\n".join(json.dumps(r) for r in STREAM) + "\n")
    expected_csv = tmp / "expected.csv"
    # Excel "CSV UTF-8" exports carry a BOM — the adapter must tolerate it.
    expected_csv.write_text(EXPECTED_CSV, encoding="utf-8-sig")

    conn = connect(tmp / "scans.db")
    summary = ingest_jsonl(conn, jsonl, mission_id="m1")
    assert summary["inserted"] == 10, summary
    assert summary["placards"] == 3, summary
    assert summary["location_tagged"] == 6, summary  # STALE-1 outside 10s window

    # idempotency: replay changes nothing
    again = ingest_jsonl(conn, jsonl, mission_id="m1")
    assert again["inserted"] == 0 and again["skipped_duplicates"] == 10, again

    # clear_mission wipes only the named mission, enabling clean re-runs
    from warehouse_scan.ingest import clear_mission
    ingest_jsonl(conn, jsonl, mission_id="other")
    assert clear_mission(conn, "m1") == 10
    assert observations(conn, "m1") == []
    assert len(observations(conn, "other")) == 6  # untouched
    redo = ingest_jsonl(conn, jsonl, mission_id="m1")
    assert redo["inserted"] == 10, redo

    from warehouse_scan.ingest import missions
    assert {m["mission_id"] for m in missions(conn)} == {"m1", "other"}
    m1 = next(m for m in missions(conn) if m["mission_id"] == "m1")
    assert m1["scans"] == 10 and m1["placards"] == 3, m1

    obs = observations(conn, "m1")
    assert len(obs) == 6, obs  # SKU, TOOL, EAN, PHANT0M, QR-ONLY, STALE
    ean = next(o for o in obs if o["barcode"] == "4006381333931")
    assert ean["sightings"] == 2 and ean["location"] == "A07-B13-L1", ean

    # placard-only bay must NOT count as visited (else false 'missing' claims)
    visited = visited_locations(conn, "m1")
    assert visited == {"A07-B12-L3", "A07-B13-L1"}, visited
    placards = placard_locations(conn, "m1")
    assert placards == {"A07-B12-L3", "A07-B13-L1", "A08-B01-L1"}, placards

    adapter = FileExchangeAdapter(expected_csv, tmp)
    verdicts = reconcile(adapter.fetch_expected(), obs, visited, placard_seen=placards)
    counts = summarize(verdicts)

    assert counts == {
        "match": 1,        # SKU-000123-A at A07-B12-L3
        "missing": 2,      # WIDGET-999 and STALE-1: bay visited, not seen there
        "unverified": 3,   # GADGET-1, TOOL-777's expected bay, EMPTY-BAY-ITEM
        "misplaced": 1,    # TOOL-777 seen at A07-B13-L1
        "unexpected": 3,   # EAN + PHANT0M-1 + QR-ONLY-1 (threshold off by default)
    }, counts

    # With min_sightings=2: one-sighting 1D accusations (the phantom AND the
    # single-read TOOL-777 misplaced claim) downgrade to low_confidence; the
    # 2-sighting EAN survives; the single-sighting QR bypasses the threshold
    # (RS-corrected symbology); matches are never gated.
    strict = reconcile(adapter.fetch_expected(), obs, visited,
                       placard_seen=placards, min_sightings=2)
    strict_counts = summarize(strict)
    phantom = next(v for v in strict if v.barcode == "PHANT0M-1")
    assert phantom.verdict == "low_confidence", phantom
    assert "1 sighting" in phantom.note, phantom
    ean_v = next(v for v in strict if v.barcode == "4006381333931")
    assert ean_v.verdict == "unexpected" and ean_v.sightings == 2, ean_v
    qr_v = next(v for v in strict if v.barcode == "QR-ONLY-1")
    assert qr_v.verdict == "unexpected" and qr_v.sightings == 1, qr_v
    assert strict_counts == {
        "match": 1, "missing": 2, "unverified": 3,
        "unexpected": 2, "low_confidence": 2,
    }, strict_counts

    # missing STALE-1 must carry its no-context sighting as evidence
    stale = next(v for v in _by_verdict(verdicts, "missing") if v.barcode == "STALE-1")
    assert "without location context" in stale.note, stale
    # placard-only bay: unverified with an explanatory note, never missing
    empty_bay = next(v for v in verdicts if v.barcode == "EMPTY-BAY-ITEM")
    assert empty_bay.verdict == "unverified", empty_bay
    assert "placard seen" in empty_bay.note, empty_bay

    misplaced = _by_verdict(verdicts, "misplaced")[0]
    assert misplaced.barcode == "TOOL-777" and misplaced.location == "A07-B13-L1"
    assert misplaced.expected_location == "A07-B14-L2"

    counts_csv = adapter.push_counts(verdicts)
    exceptions_csv = adapter.push_exceptions(verdicts)
    assert counts_csv.exists() and exceptions_csv.exists()
    exception_lines = exceptions_csv.read_text().strip().splitlines()
    assert len(exception_lines) == 1 + (len(verdicts) - counts["match"])

    conn.close()
    print("PASS: ingest -> reconcile -> file adapter, all verdicts correct")


if __name__ == "__main__":
    test_pipeline()
