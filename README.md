# Upright — Autonomous Warehouse Inventory Scanning

Goal: autonomously fly a drone through a warehouse and read inventory barcodes,
matching them to rack/aisle locations.

## ⚠️ Read this first: the Skydio R1 reality check

You asked to use the **Skydio R1** and "find/set up its SDK." After researching
the current (2026) state of things, here is the honest situation:

- The **Skydio R1 is a discontinued 2018 consumer drone.** Its Python
  **"Skills SDK"** (the thing that let you write custom onboard autonomy/perception)
  was **invite-only even when new**, and there is **no supported, installable R1
  SDK today**. Skydio's GitHub org now ships only
  [`skydio-cloud-api-examples`](https://github.com/Skydio/skydio-cloud-api-examples);
  the old skills code only survives as stale community forks. So **there is no
  "R1 SDK" to set up.**
- Skydio's **current** developer surface ("Skydio Extend") targets the
  **enterprise X10 / X10D**, not the R1:
  - **Cloud API** — public, JWT REST/JSON ([apidocs.skydio.com](https://apidocs.skydio.com)):
    plan/launch missions, pull telemetry, live RTSP video, and **download captured
    media**. *Not* low-level real-time control, *not* custom onboard perception.
  - **Control & Telemetry ICD** (MAVLink / RAS-A) — real-time command & control,
    **X10D only**, access-gated (defense/partner).
  - There is **no public way to run a custom onboard "barcode skill"** on current
    Skydio hardware like the R1 once allowed.
- **Barcode-from-a-drone is real but specialized.** Companies like
  **Corvus Robotics** (Corvus One: 12 nav cameras + an *industrial* barcode scanner,
  flies lights-out, no beacons), **Gather AI**, and **Verity** sell this as a
  managed **Robot-as-a-Service**. The hard part is **not** decoding the barcode —
  it's **GPS-denied indoor autonomy**, safe flight in cluttered racking, and
  barcode **optics/lighting** at standoff distance.

**Bottom line:** the R1 is the wrong starting point. See [docs/PLAN.md](docs/PLAN.md)
for the three realistic paths (buy turnkey / build DIY / Skydio-enterprise) and a
recommendation. For the **DIY build decision** — DJI+Marvelmind vs. building your
own, with parts lists, prices, and a step-by-step — see [docs/BUILD.md](docs/BUILD.md).
Bills of materials: [PX4 + Marvelmind](docs/BOM-px4-marvelmind.md) ·
[PX4 + VIO, no beacons](docs/BOM-px4-vio.md) ·
[**vision-only $2k demo drone**](docs/BOM-vision-demo.md) (chosen for the initial demo).
WMS integration plan: [docs/WMS-INTEGRATION.md](docs/WMS-INTEGRATION.md).
**Current demo (human-piloted DJI Mini 4 Pro → RTMP → live laptop decode):
[docs/DEMO-RTMP.md](docs/DEMO-RTMP.md).**

## What this repo gives you *today*

The one part that is real software work and is **useful no matter which drone you
land on** is the **barcode/QR perception pipeline**. This repo sets that up so you
can prove it on a webcam or video right now, plus a stub for the realistic Skydio
path (fly missions → pull media via Cloud API → decode off-board).

```
warehouse_scan/
  detector.py      # core: decode 1D/2D barcodes from images/video/webcam frames
  cli.py           # `python -m warehouse_scan ...` entry point
  skydio_cloud.py  # Skydio Cloud API client stub (list flights, download media)
scripts/
  make_test_barcodes.py   # generate sample barcodes to test the pipeline offline
docs/PLAN.md       # the full plan + path comparison
```

## Quick start

```bash
# 1. Native dependency for pyzbar (macOS):
brew install zbar

# 2. Python env + deps:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Prove the perception pipeline works (no hardware needed):
python scripts/make_test_barcodes.py          # writes sample_data/*.png
python -m warehouse_scan dir sample_data       # decodes them

# 4. Live test with your laptop webcam (press q to quit):
python -m warehouse_scan webcam

# 5. (DIY build, Phase 1) Measure read-rate vs drone-flight conditions:
python -m warehouse_scan benchmark sample_data
#   -> derives the camera resolution / flight-speed / lighting your build needs.
#      Best run on photos of YOUR real labels, not just the synthetic samples.
```

## Skydio Cloud path (only if you go enterprise)

`warehouse_scan/skydio_cloud.py` is a thin client for the **public** Cloud API.
It needs an enterprise org token (set `SKYDIO_API_TOKEN` / `SKYDIO_API_TOKEN_ID`,
see [.env.example](.env.example)). It can list flights and download captured media
so you can run `detector.py` over the imagery. This is the *only* Skydio-flavored
architecture available without the gated real-time ICD.

See [docs/PLAN.md](docs/PLAN.md) for the phased roadmap.
