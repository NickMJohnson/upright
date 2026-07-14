# Demo runbook — DJI Mini 4 Pro → RTMP → laptop barcode identification

Human-piloted demo: the Mini 4 Pro streams live video via DJI Fly's RTMP output
to a laptop, which decodes barcodes in real time.

```
Mini 4 Pro ──OcuSync──▶ RC / phone (DJI Fly) ──RTMP over Wi-Fi──▶ laptop
                                                    mediamtx :1935
                                                        │
                                     python -m warehouse_scan stream ...
                                     live overlay + results/stream.jsonl
```

**Status: laptop side verified end-to-end** (2026-06-29) with a simulated
1080p H.264 RTMP feed — all three test symbologies (Code128, EAN-13, QR)
decoded live. The drone simply replaces the simulator.

## One-time setup (laptop)

```bash
brew install mediamtx            # RTMP/RTSP relay, single binary
cd ~/Desktop/projects/upright
source .venv/bin/activate        # deps already installed (README quick start)
```

## Demo day — laptop (2 terminals)

```bash
# Terminal 1 — start the RTMP server:
mediamtx config/mediamtx.yml

# Find your laptop's LAN IP (needed by DJI Fly):
ipconfig getifaddr en0           # e.g. 192.168.1.42

# Terminal 2 — start the live decoder (preview window + JSONL log):
python -m warehouse_scan stream rtmp://localhost:1935/live/drone
```

Notes:
- macOS may prompt to allow mediamtx to accept incoming connections — allow it.
- Unique reads print to the console and append to `results/stream.jsonl`
  (with UTC timestamps); the preview window draws green boxes on decodes.
- Headless/logging-only: add `--no-display`. Tune `--stride N` if CPU-bound.

## Demo day — drone (DJI Fly)

1. Put the **phone running DJI Fly on the same Wi-Fi as the laptop**. (The
   RC↔drone link is OcuSync and unaffected; the phone's Wi-Fi carries the RTMP.)
2. DJI Fly → **GO FLY → ⋯ → Transmission → Live Streaming Platforms → RTMP**.
3. Enter: `rtmp://<LAPTOP-IP>:1935/live/drone`  (e.g. `rtmp://192.168.1.42:1935/live/drone`).
4. Set stream quality to **1080p**, highest bitrate offered.
5. Start streaming; the decoder window shows the feed within a few seconds.

## Flying for good reads (compressed 1080p is the constraint)

- **Hover at each label** 1–2 s; read-then-move. RTMP compression + rolling
  shutter means in-motion 1D reads are unreliable — stationary reads work.
- Get close: fill ~1/4 of the frame width with the label (our benchmark:
  ~140–200 px across the code minimum; more is better after compression).
- Square-on to the label (±20°), good lighting; avoid backlight/glare.
- **QR codes and large-module Code128 read far better than dense retail 1D**
  through compression — for the demo, favor pallet/location labels or print
  test labels large.
- Expect 2–5 s of glass-to-decode latency (normal for RTMP; fine for a demo).

## Suggested demo script (15 min)

1. Pre-flight: start both terminals; verify with a handheld printed QR in
   front of the drone on the ground — decode appears before takeoff.
2. Fly a slow pass down one rack section, hovering at 4–6 labeled positions.
3. Land; open `results/stream.jsonl` — show captured codes + timestamps.
4. (Optional wow) Also record 4K onboard; after landing, run
   `python -m warehouse_scan video /path/to/sdcard_clip.MP4` and show the
   *higher* read rate from full-quality footage — this motivates the
   production architecture (decode from raw frames, not compressed streams).

## Known limits of this demo rig (talking points, not blockers)

- Human pilot (autonomy comes later — see docs/BOM-vision-demo.md build).
- Compressed stream lowers 1D read rate → production decodes onboard/from raw.
- No location tagging yet → next step is placard QRs so each read pairs with
  an `AISLE/BAY/LEVEL` code in the same pass (works today: both decode together).
- Scans land in a JSONL file → feeds Phase 1 of docs/WMS-INTEGRATION.md as-is.

## Next steps after the demo

1. Print **location placard QRs** for a few bays — instant location-tagged scans.
2. Stand up WMS Phase 1–2 (`ingest` + `reconcile`) replaying `stream.jsonl`.
3. Compare live-stream vs onboard-4K read rates on your real labels — this
   number decides how much the future build must rely on onboard decode.
