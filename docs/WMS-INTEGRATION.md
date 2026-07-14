# WMS integration plan — from drone scans to inventory truth

> Status: Phases 1–2 and the tier-1 adapter are implemented — see
> `warehouse_scan/ingest.py`, `warehouse_scan/reconcile.py`, `warehouse_scan/wms.py`,
> CLI commands `ingest` / `reconcile`, and `tests/test_wms_pipeline.py`.

Goal: turn raw drone scans into WMS-grade inventory updates, safely. The guiding
principle (from how commercial systems like Corvus/Gather work): **the drone
system is a cycle-count feed, not a second source of truth.** It never writes
live inventory directly; it produces evidence that the WMS (or a human) accepts.

## Architecture recap

```
drone (Pi 5)                    ground server (laptop/mini-PC)          WMS
────────────                    ──────────────────────────────          ───
capture → decode →  ──JSON──▶   ingest → dedupe → reconcile  ──────▶   adapter
tag location, queue  (Wi-Fi)    (SQLite/Postgres)  vs expected          (tiered)
```

The drone emits scan records; all WMS logic lives server-side. The drone never
holds WMS credentials.

## Phase 0 — Data contract (do this first; everything hangs off it)

**Scan record** (drone → server), one JSON object per read:

```json
{
  "scan_id": "uuid",
  "ts": "2026-06-29T14:03:22Z",
  "barcode": "00123456789012345675",
  "symbology": "CODE128",
  "location": {
    "placard": "A07-B12-L3",
    "source": "placard | pose | pose+placard",
    "pose_xyz": [4.21, 1.10, 3.40],
    "confidence": 0.92
  },
  "mission_id": "2026-06-29-aisle07",
  "frame_ref": "optional path to saved image for audit"
}
```

Key decisions to lock with whoever runs the WMS:
1. **What do the barcodes encode?** Retail UPC/EAN on cartons, GS1-128 with
   SSCC on pallets (LPN — license plate number), or internal SKU labels? The
   reconciliation joins on this — get real samples early. (Our Phase-1 benchmark
   on real labels answers readability *and* symbology at once.)
2. **Location naming:** placard IDs must map 1:1 to WMS location codes
   (`A07-B12-L3` ↔ the WMS's bin/slot naming). Decide the scheme *before*
   printing placards.
3. **Coverage semantics:** a drone sees pallet *faces*. A location with no
   readable code is "unverified", not "empty" — the contract must distinguish
   `scanned-empty` vs `not-scanned` vs `unreadable`.

## Phase 1 — Ground ingest + store (pure software, no drone needed)

- Receiver service (MQTT subscriber or HTTPS endpoint) → validates records →
  appends to an **append-only** `scans` table (SQLite to start; Postgres when
  multi-user). Idempotent on `scan_id` (drone store-and-forward may resend).
- Dedupe pass: collapse repeat reads of the same barcode at the same location
  within a mission window; keep max-confidence read; count sightings.
- Deliverable: `warehouse_scan/ingest.py` + `scans.db`. Testable today by
  replaying `results/scan.jsonl` from bench tests.

## Phase 2 — Reconciliation engine (the actual value)

Input: deduped observations + an **expected-inventory snapshot** exported from
the WMS (CSV/API) at mission start. Output: per-location verdicts:

| Verdict | Meaning | Typical action |
|---|---|---|
| `match` | expected item seen at expected location | confirm count |
| `misplaced` | item seen, but WMS thinks it's elsewhere | move task / recount |
| `missing` | location scanned readable-empty but WMS expects stock | recount task |
| `unexpected` | item seen that WMS doesn't place here | investigate |
| `unverified` | not scanned / unreadable | exclude from claims |

Rules that keep this trustworthy:
- **Snapshot windowing:** inventory moves during flights. Only reconcile
  locations with no WMS transactions between snapshot and scan time; flag the
  rest `stale — recount`.
- Every verdict links back to its scan_ids (and saved frames) for audit.
- Thresholds: e.g. require ≥2 sightings or confidence ≥ X before asserting
  `misplaced`/`missing`.
- Deliverable: `warehouse_scan/reconcile.py` + an exceptions report
  (CSV/HTML). Testable with a mock expected-inventory file.

## Phase 3 — WMS adapter (tiered; start at tier 1 no matter what)

A single interface, three interchangeable backends:

```python
class WmsAdapter:
    def fetch_expected(self, locations) -> list[ExpectedRecord]: ...
    def push_counts(self, verdicts) -> Receipt: ...       # cycle-count entries
    def push_exceptions(self, verdicts) -> Receipt: ...   # tasks/alerts
```

- **Tier 1 — File exchange (works with every WMS, human-in-loop):** import the
  WMS's inventory export (CSV/XLSX); emit a cycle-count import file in the WMS's
  format + an exceptions report for a supervisor. *Ship this first* — it proves
  value with zero integration risk.
- **Tier 2 — API:** direct calls to the WMS's cycle-count/inventory-adjustment
  endpoints (NetSuite REST, SAP EWM OData, Odoo XML-RPC, Fishbowl, Infor, etc.).
  Adjustments go in as *proposed* counts wherever the WMS supports approval
  workflows.
- **Tier 3 — Staging/EDI:** SFTP flat-file drops or a staging DB table the WMS
  polls — common for legacy/on-prem systems.

Security: adapter credentials live only on the ground server (env/secret store);
append-only audit log of everything pushed; per-mission dry-run mode that
produces the files/calls without sending.

## Phase 4 — Operational loop

- Mission scheduler: recurring counts by zone (cron on the ground server);
  each mission = zone + expected snapshot + flight plan.
- Coverage dashboard: % of locations verified this week, exception aging,
  read-rate per aisle (feeds back into flight tuning).
- Human workflow: supervisor reviews exceptions → approves adjustments in the
  WMS → system tracks which exceptions cleared.

## Build order & effort (software only; drone can arrive in parallel)

| Step | Depends on | Effort |
|---|---|---|
| 0. Data contract + placard/location scheme agreed | WMS owner conversation | days |
| 1. Ingest + store + dedupe | nothing — replay bench scans | ~1 week |
| 2. Reconcile + exceptions report | mock expected CSV | 1–2 weeks |
| 3. Tier-1 file adapter (real WMS export/import formats) | real WMS exports | ~1 week |
| 4. Pilot: manual walk-through scans → full loop → supervisor review | 1–3 | 1 week |
| 5. Tier-2 API adapter (if the WMS has one) | pilot learnings | 1–3 weeks |

Note step 4: the whole WMS loop can be **piloted with a handheld phone/webcam
walking the aisles** before the drone ever flies — same decoder, same records,
same reconciliation. That de-risks the integration completely independently of
flight work.

## Success metrics

- Verified-location coverage per mission (%)
- Read rate: decoded / attempted label-positions
- Exception precision: % of flagged exceptions confirmed real by recount
  (this is the trust metric — target high precision early, even at low recall)
- Time from scan to supervisor-ready report

## Open questions (answer before Phase 3)

1. **Which WMS** (or none/spreadsheet today)? Determines adapter tier + formats.
2. Barcode content on your labels (SKU vs LPN/SSCC vs internal)?
3. Who owns approval of adjustments (supervisor workflow vs auto-apply)?
4. Location naming scheme to mirror on placards?
