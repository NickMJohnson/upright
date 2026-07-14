"""Reconciliation engine (Phase 2 of docs/WMS-INTEGRATION.md).

Joins deduped observations against an expected-inventory snapshot and emits
per-row verdicts. Coverage semantics are strict: a location we never visited
yields `unverified`, never `missing` — the drone not looking is not evidence
of absence.

Verdicts:
  match       expected item observed at its expected location
  missing     location was visited, expected item not seen there
  misplaced   item observed at a location it is not expected at
  unexpected  observed item that appears nowhere in the expected snapshot
  unverified  expected location never item-scanned — no claim made (a placard
              glimpse alone does not count as visiting; see visited_locations)
  low_confidence  observation below the sightings threshold — kept in the
              cycle-count audit trail but excluded from the exceptions report.
              Corrupted reads that beat a barcode checksum (common off phone
              screens, rare off paper) appear once; real labels re-read
              consistently, so `min_sightings=2` filters phantoms cheaply.

The threshold only gates accusations (misplaced/unexpected). Matches count at
any sighting level — filtering observations out of matching could fabricate
false `missing` claims.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Verdict:
    verdict: str
    barcode: str
    location: str | None = None           # where it was observed (if observed)
    expected_location: str | None = None  # where the WMS expects it
    sightings: int = 0
    note: str = ""


def reconcile(
    expected: list[dict],
    observations: list[dict],
    visited: set[str],
    placard_seen: set[str] | None = None,
    min_sightings: int = 1,
) -> list[Verdict]:
    """expected: [{location, barcode, ...}]; observations: from ingest.observations().

    visited: locations with >=1 location-tagged ITEM read (ingest.visited_locations).
    placard_seen: locations whose placard was decoded (ingest.placard_locations) —
    used only to annotate `unverified` rows; a placard glimpse alone never
    enables a `missing` claim.
    min_sightings: observations seen fewer times than this are downgraded to
    `low_confidence` instead of generating misplaced/unexpected claims.
    """
    placard_seen = placard_seen or set()
    exp_locs: dict[str, set[str]] = defaultdict(set)
    for row in expected:
        exp_locs[row["barcode"]].add(row["location"])

    obs_index: dict[tuple[str, str | None], dict] = {}
    obs_locs: dict[str, set[str]] = defaultdict(set)
    obs_no_ctx: dict[str, int] = defaultdict(int)  # sightings without location context
    for o in observations:
        obs_index[(o["barcode"], o["location"])] = o
        if o["location"] is not None:
            obs_locs[o["barcode"]].add(o["location"])
        else:
            obs_no_ctx[o["barcode"]] += o["sightings"]

    def _evidence(bc: str, exclude: str) -> str:
        parts = []
        elsewhere = sorted(obs_locs.get(bc, set()) - {exclude})
        if elsewhere:
            parts.append(f"seen at {', '.join(elsewhere)}")
        if obs_no_ctx.get(bc):
            parts.append(f"read {obs_no_ctx[bc]}x without location context")
        return "; ".join(parts)

    verdicts: list[Verdict] = []

    # Expected side: match / missing / unverified per expected row.
    for row in expected:
        bc, loc = row["barcode"], row["location"]
        hit = obs_index.get((bc, loc))
        if hit:
            verdicts.append(Verdict("match", bc, loc, loc, hit["sightings"]))
        elif loc in visited:
            verdicts.append(Verdict("missing", bc, None, loc, 0, _evidence(bc, loc)))
        else:
            base = ("placard seen, but no item reads at location"
                    if loc in placard_seen else "location not visited")
            extra = _evidence(bc, loc)
            note = f"{base}; {extra}" if extra else base
            verdicts.append(Verdict("unverified", bc, None, loc, 0, note))

    # Observed side: misplaced (known item, wrong place) / unexpected (unknown item).
    # Known barcodes read without location context are surfaced via the
    # expected-side evidence notes above, not as separate verdicts.
    def _accuse(kind: str, bc: str, loc: str | None, exp: str | None, o: dict,
                note: str = "") -> Verdict:
        if o["sightings"] < min_sightings:
            detail = f"would be '{kind}' but only {o['sightings']} sighting(s)"
            return Verdict("low_confidence", bc, loc, exp, o["sightings"],
                           f"{detail}; {note}" if note else detail)
        return Verdict(kind, bc, loc, exp, o["sightings"], note)

    for o in observations:
        bc, loc = o["barcode"], o["location"]
        if loc is None:
            if bc not in exp_locs:
                verdicts.append(
                    _accuse("unexpected", bc, None, None, o,
                            "no location context for this read")
                )
            continue
        if bc in exp_locs:
            if loc not in exp_locs[bc]:
                verdicts.append(
                    _accuse("misplaced", bc, loc,
                            ", ".join(sorted(exp_locs[bc])), o)
                )
        else:
            verdicts.append(_accuse("unexpected", bc, loc, None, o))

    return verdicts


def summarize(verdicts: list[Verdict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for v in verdicts:
        counts[v.verdict] += 1
    return dict(counts)
