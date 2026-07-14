# No-drone test walkthrough — you are the drone

End-to-end test of the entire scanning → WMS pipeline using a laptop webcam.
Takes ~15 minutes, needs no hardware beyond your laptop (and optionally a
printer). Every stage a real flight exercises runs here: decode → location
tagging → ingest → reconciliation → supervisor report.

## 1. What you need

Generate the test codes (if `sample_data/` and `placards/` don't already exist):

```bash
cd <repo> && source .venv/bin/activate
python scripts/make_test_barcodes.py          # item labels -> sample_data/
python scripts/make_placards.py A07-B12-L3 A07-B13-L1 A08-B01-L1   # -> placards/
```

You'll use six images:

| File | Role | Payload |
|---|---|---|
| `placards/A07-B12-L3.png` | bay 1 placard | `LOC:A07-B12-L3` |
| `placards/A07-B13-L1.png` | bay 2 placard | `LOC:A07-B13-L1` |
| `placards/A08-B01-L1.png` | bay 3 placard | `LOC:A08-B01-L1` |
| `sample_data/qr_sku.png` (or `code128_sku.png`) | item at bay 1 | `SKU-000123-A` |
| `sample_data/qr_tool777.png` (or `code128_tool777.png`) | item at bay 2 | `TOOL-777` |
| `sample_data/qr_ean.png` (or `ean13_product.png`) | item at bay 2 | `4006381333931` |

**Screen or paper?**
- **QR versions on a phone screen work great** — Reed–Solomon correction makes
  them immune to screen moiré. Brightness up, avoid glare.
- **1D versions (code128/ean13) should be printed.** Displayed on a screen they
  produce occasional *misreads* (moiré artifacts that pass the checksum). This
  is actually a useful stress test of the `--min-sightings` filter — run 1D
  from the screen once on purpose to watch phantoms get caught.

The "WMS says" file is committed at [demo/expected.csv](../demo/expected.csv).
Each row's description names the verdict it is designed to produce.

## 2. Placing the codes

Two setups, same commands either way:

**Desk test (fastest):** keep the six images open on your phone; you'll show
them to the webcam one at a time in the order below, ~20–40 cm from the lens.

**Simulated aisle (more realistic):** tape each placard to a wall/shelf spot a
few meters apart — those are your "bays" — and tape/hold each bay's item labels
next to its placard. Walk the laptop (or use a long-cable/continuity webcam)
from bay to bay like a drone would fly.

Placement rules (same physics as the drone):
- Code should fill roughly **¼ of the frame width**; too far = no read.
- Face the camera squarely (within ~20°), avoid glare/backlight.
- Hold each code steady until the terminal prints it (~1–3 s).
- **Placard first, then that bay's items** — items inherit the location of the
  most recent placard (30 s window with the flags below).

## 3. The walk script

Show codes in exactly this order:

| # | Show | Story it plays out |
|---|---|---|
| 1 | placard `A07-B12-L3` | arrive at bay 1 |
| 2 | item `SKU-000123-A` | found where expected → **match** |
| 3 | placard `A07-B13-L1` | arrive at bay 2 |
| 4 | item `TOOL-777` | WMS expects it at B14 → **misplaced** |
| 5 | item `4006381333931` | not in the WMS at all → **unexpected** |
| 6 | placard `A08-B01-L1` | bay 3: placard only, show **no items** → **unverified** |

Never shown, on purpose: `WIDGET-999` (expected at bay 1 → **missing**) and
bay `A09-B01-L1` (never visited → **unverified**).

## 4. Commands

```bash
# fresh session (webcam appends across runs; clear it)
rm -f results/webcam.jsonl

# 1. the walk — press q in the preview window when done
python -m warehouse_scan webcam --relog-interval 1

# 2. raw reads -> located observations (pick a fresh mission name per run)
python -m warehouse_scan ingest results/webcam.jsonl --mission test1 --window 30

# 3. observations vs expected inventory -> verdicts + reports
python -m warehouse_scan reconcile --expected demo/expected.csv \
    --mission test1 --min-sightings 2
```

Flag cheat-sheet:
- `--relog-interval 1` — re-log a still-visible code every second, so holding a
  label ~3 s yields ~3 sightings (sightings gate 1D misread filtering).
- `--window 30` — items inherit the last placard's location for 30 s (drone
  missions use a tighter window; humans fumble phones).
- `--min-sightings 2` — 1D codes seen only once become `low_confidence` instead
  of generating misplaced/unexpected claims. QR reads bypass this (their error
  correction means a decoded QR can't be a plausible-but-wrong string).

## 5. What success looks like

Reconcile console output:

```
Expected rows: 5, observations: 3, visited locations: 2, min sightings: 2
  match       1
  missing     1
  misplaced   1
  unexpected  1
  unverified  3
```

(`observations` may be a little higher if stray reads occurred — see §6.
A `low_confidence` line may appear; that's the filter working, not a failure.)

`results/exceptions.csv` — the supervisor report — should contain exactly:

```
verdict,barcode,location,expected_location,sightings,note
missing,WIDGET-999,,A07-B12-L3,0,
unverified,TOOL-777,,A07-B14-L2,0,location not visited; seen at A07-B13-L1
unverified,FREEZER-KIT,,A08-B01-L1,0,"placard seen, but no item reads at location"
unverified,GADGET-1,,A09-B01-L1,0,location not visited
unexpected,4006381333931,A07-B13-L1,,N,
misplaced,TOOL-777,A07-B13-L1,A07-B14-L2,N,
```

(`N` = your sighting counts; the match row lives in `cycle_counts.csv`, which
also keeps any `low_confidence` rows as an audit trail.)

Reading the three `unverified` notes is the point of the design:
- TOOL-777's expected bay was never visited — but the note carries the evidence
  ("seen at A07-B13-L1") that pairs with its `misplaced` row.
- FREEZER-KIT's bay had its **placard seen but no item reads** — the pipeline
  refuses to call it `missing`, because glimpsing a placard isn't inspecting a
  shelf.
- GADGET-1's bay was simply never visited.

## 6. If your output differs

| Symptom | Likely cause | Fix |
|---|---|---|
| `match 0`, SKU shows as `unexpected` at no location | item shown before its placard, or > window after it | placard first; `--window 30`; re-show placard on revisits |
| A designed verdict missing entirely | that code never got a steady read (check terminal during the walk) | hold until it prints; closer; less glare |
| Extra `unexpected` with 1 sighting | one-off 1D misread (screen moiré, or the 1D decoder firing on background stripes) | that's what `--min-sightings 2` catches — check it moved to `low_confidence` in cycle_counts.csv |
| Extra `unexpected` with 2+ sightings, gibberish-looking | *systematic* screen misread — stable moiré reproduces the same wrong decode | print that label; screens are a worst-case stress test |
| Everything `unverified` | reconcile ran against the wrong `--db`/`--mission` | mission names must match between ingest and reconcile |
| `ingest` reports `location_tagged=0` | placards never decoded (too small/far) or wrong prefix | placards need `LOC:` payloads — use `scripts/make_placards.py` output |

## 7. Variations worth running

- **Symbology A/B:** run once with the `code128_*`/`ean13_*` files from a phone
  screen, once with the `qr_*` files. Compare `low_confidence` counts — this
  reproduces the experiment that set the project's "QR wherever we control the
  label" policy.
- **Idempotency:** run `ingest` twice with the same mission — second run
  reports `inserted=0`; verdicts don't change.
- **Same walk, new mission:** re-walk and ingest with `--mission test2` —
  missions are isolated; reconcile each independently.

When the DJI Mini 4 Pro arrives, this exact test moves onto the drone by
replacing step 1 with `python -m warehouse_scan stream rtmp://localhost:1935/live/drone`
(see [DEMO-RTMP.md](DEMO-RTMP.md)) — everything from ingest onward is identical.
