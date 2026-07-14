"""WMS adapter layer (Phase 3 of docs/WMS-INTEGRATION.md).

One interface, swappable backends. Tier 1 (file exchange) is implemented here:
it reads the WMS's expected-inventory CSV export and writes cycle-count and
exceptions CSVs a supervisor can import/review. API and staging-table adapters
implement the same three methods later.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from .reconcile import Verdict


class WmsAdapter(Protocol):
    def fetch_expected(self) -> list[dict]: ...
    def push_counts(self, verdicts: list["Verdict"]) -> Path: ...
    def push_exceptions(self, verdicts: list["Verdict"]) -> Path: ...


class FileExchangeAdapter:
    """Tier 1: CSV in, CSV out. Works with any WMS; human-in-the-loop.

    Expected-inventory CSV columns: location, barcode[, description].
    Extra columns are preserved into the description field if present.
    """

    def __init__(self, expected_csv: str | Path, out_dir: str | Path = "results"):
        self.expected_csv = Path(expected_csv)
        self.out_dir = Path(out_dir)

    def fetch_expected(self) -> list[dict]:
        rows: list[dict] = []
        # utf-8-sig strips the BOM Excel prepends to "CSV UTF-8" exports
        with self.expected_csv.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            cols = {c.lower().strip(): c for c in (reader.fieldnames or [])}
            if "location" not in cols or "barcode" not in cols:
                raise ValueError(
                    f"{self.expected_csv}: need 'location' and 'barcode' columns, "
                    f"got {reader.fieldnames}"
                )
            for r in reader:
                location = (r.get(cols["location"]) or "").strip()
                barcode = (r.get(cols["barcode"]) or "").strip()
                if not location or not barcode:
                    continue
                rows.append(
                    {
                        "location": location,
                        "barcode": barcode,
                        "description": (r.get(cols.get("description", ""), "") or "").strip(),
                    }
                )
        return rows

    def _write(self, name: str, verdicts: list["Verdict"]) -> Path:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        out = self.out_dir / name
        with out.open("w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                ["verdict", "barcode", "location", "expected_location",
                 "sightings", "note"]
            )
            for v in verdicts:
                writer.writerow(
                    [v.verdict, v.barcode, v.location or "",
                     v.expected_location or "", v.sightings, v.note]
                )
        return out

    def push_counts(self, verdicts: list["Verdict"]) -> Path:
        return self._write("cycle_counts.csv", verdicts)

    def push_exceptions(self, verdicts: list["Verdict"]) -> Path:
        # low_confidence rows stay in cycle_counts.csv (audit trail) but are
        # kept out of the supervisor-facing exceptions report.
        return self._write(
            "exceptions.csv",
            [v for v in verdicts if v.verdict not in ("match", "low_confidence")],
        )
