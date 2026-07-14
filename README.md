# Upright — Warehouse Inventory Scanning by Drone

Scan warehouse inventory barcodes from a drone and reconcile the results against
the warehouse management system.

## Current direction

**Phase A (now): piloted demo.** A human-flown **DJI Mini 4 Pro** live-streams
video (DJI Fly → RTMP over Wi-Fi) to a laptop, which decodes barcodes in real
time and logs `{barcode, timestamp}` records. The laptop pipeline is built and
verified end-to-end against a simulated 1080p drone feed.
→ Runbook: **[docs/DEMO-RTMP.md](docs/DEMO-RTMP.md)**

**Phase B: autonomous platform.** A PX4-based QAV250 build (optical flow +
downward LiDAR for GPS/beacon-free indoor positioning, Raspberry Pi 5 companion,
global-shutter camera for onboard decode) flies scripted aisle missions.
→ Parts list: **[docs/BOM-vision-demo.md](docs/BOM-vision-demo.md)** ·
background: **[docs/BUILD.md](docs/BUILD.md)**

**Phase C: WMS integration.** Scan records become a cycle-count feed — ingest,
dedupe, reconcile against expected stock, and push counts/exceptions to the WMS.
→ Plan: **[docs/WMS-INTEGRATION.md](docs/WMS-INTEGRATION.md)**

## What's in this repo

```
warehouse_scan/
  detector.py    # core: decode 1D/2D barcodes in frames (pyzbar + OpenCV)
  benchmark.py   # read-rate vs distance/angle/blur/lighting harness
  ingest.py      # decoder JSONL -> SQLite scan store (placard location tagging)
  reconcile.py   # observations vs expected inventory -> verdicts
  wms.py         # WMS adapter interface + tier-1 CSV file exchange
  cli.py         # image | dir | video | webcam | stream | benchmark | ingest | reconcile
config/mediamtx.yml        # RTMP server config for the live demo
scripts/make_test_barcodes.py   # generate sample codes (no hardware needed)
scripts/make_placards.py        # printable rack-bay location QR placards
tests/test_wms_pipeline.py      # end-to-end: scans -> ingest -> reconcile -> CSVs
docs/                      # runbook, BOMs, build guide, WMS plan
```

## From scans to a WMS report

```bash
# after a flight (or handheld walk-through) produced results/stream.jsonl:
python -m warehouse_scan ingest results/stream.jsonl --mission aisle07
python -m warehouse_scan reconcile --expected expected.csv --mission aisle07
# -> results/cycle_counts.csv + results/exceptions.csv
```

`expected.csv` is a WMS export with `location,barcode[,description]` columns.
Rack placards for location tagging: `python scripts/make_placards.py A07-B12-L3 ...`

## Quick start

```bash
# 1. Native dependency for pyzbar (macOS):
brew install zbar

# 2. Python env + deps:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Prove the pipeline (no hardware needed):
python scripts/make_test_barcodes.py
python -m warehouse_scan dir sample_data

# 4. Live webcam test (press q to quit):
python -m warehouse_scan webcam

# 5. Measure read-rate vs drone-flight conditions on YOUR labels:
python -m warehouse_scan benchmark sample_data
```

## Live drone demo (DJI Mini 4 Pro)

```bash
brew install mediamtx
mediamtx config/mediamtx.yml                 # terminal 1: RTMP server
python -m warehouse_scan stream rtmp://localhost:1935/live/drone   # terminal 2
```

Point DJI Fly's RTMP output at `rtmp://<laptop-ip>:1935/live/drone` (phone on
the same Wi-Fi). Full steps, flying tips, and demo script:
[docs/DEMO-RTMP.md](docs/DEMO-RTMP.md).

## Docs index

| Doc | What it covers |
|---|---|
| [docs/TEST-WALKTHROUGH.md](docs/TEST-WALKTHROUGH.md) | **No-drone webcam test: placement, commands, expected output** |
| [docs/DEMO-RTMP.md](docs/DEMO-RTMP.md) | Current demo runbook (Mini 4 Pro → RTMP → live decode) |
| [docs/PLAN.md](docs/PLAN.md) | Roadmap + platform decision log |
| [docs/BOM-vision-demo.md](docs/BOM-vision-demo.md) | QAV250 autonomous build parts list (~$1.1–1.3k) |
| [docs/BUILD.md](docs/BUILD.md) | Platform research: DJI vs open autopilot, localization options |
| [docs/BOM-px4-marvelmind.md](docs/BOM-px4-marvelmind.md) | Beacon-positioning build variant (deferred) |
| [docs/BOM-px4-vio.md](docs/BOM-px4-vio.md) | VIO production-path BOM (obstacle avoidance included) |
| [docs/WMS-INTEGRATION.md](docs/WMS-INTEGRATION.md) | WMS integration plan (cycle-count feed model) |
