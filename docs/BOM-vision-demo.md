# BOM — vision-only demo drone (no GPS, no beacons) · budget $2,000

Goal: a drone that navigates indoors **without GPS or beacons**, doesn't need
obstacle avoidance, and **decodes barcodes locally onboard** (plus can stream a
live feed). This is the "optical flow + rangefinder" architecture PX4 documents
for indoor flight — the cheapest credible vision-only navigation.

## How navigation works (no GPS, no beacons)

1. **Optical flow (PMW3901, downward-facing)** tracks floor texture like an
   upside-down mouse sensor → horizontal velocity.
2. **Downward LiDAR rangefinder** gives height above floor.
3. PX4 **EKF2** fuses flow + LiDAR + IMU → stable indoor Position-hold with zero
   external infrastructure.
4. Simple autonomous moves = **offboard velocity/position setpoints** from the
   Pi over ROS 2 (uXRCE-DDS): "fly a slow rectangle in the bay, pause at each
   label." Dead-reckoning drifts slowly, so keep missions short/slow.
5. *(Optional, free)* **AprilTag/QR placards** on racks re-anchor position and
   location-tag each scan — same trick as the production design.

## Bill of materials (~$1,600 core)

| # | Item | Role | ~USD |
|---|---|---|---|
| 1 | Holybro **X500 V2 PX4 Development Kit** (Pixhawk 6C, 915 MHz) | Frame, motors, ESCs, props, FC, power module, telemetry — one box, ~30 min assembly, no soldering | $800–885 |
| 2 | Holybro **PMW3901 optical flow** sensor (UART) | Beacon-free horizontal velocity | $40 |
| 3 | **TFmini-S / TF-Luna** downward LiDAR | Height above floor (flow needs it) | $30–50 |
| 4 | **Raspberry Pi 5 (8 GB)** + SD + active cooler | Companion: runs `warehouse_scan` decode locally, ROS 2 offboard node, streaming | $120 |
| 5 | **Arducam AR0234 global-shutter** USB3 camera, forward-facing | Barcode reads without motion smear | $170 |
| 6 | LED light bar (forward) | Even label illumination | $30 |
| 7 | 4S 5000 mAh LiPo ×2 | ~15–20 min flights each | $100 |
| 8 | LiPo balance charger | Skip if you have one | $80 |
| 9 | UBEC 5 V/5 A | Powers Pi + camera from flight battery | $15 |
| 10 | RadioMaster Pocket (ELRS) + receiver | Safety-pilot manual override — non-negotiable | $95 |
| 11 | Prop guards, spare props, mounts, cables, zip ties | Flying indoors near things | $100 |
| | **Core total** | | **~$1,580–1,685** |

Remaining budget (~$300): tax/shipping, a third battery, or a spare arm/motor.
All software is free: PX4 v1.17, QGroundControl, ROS 2 Jazzy, Micro-XRCE-DDS,
`warehouse_scan` (this repo), mediamtx for streaming, `apriltag_ros`.

## Purchase links (verified 2026-06-29)

| Item | Link | Price seen |
|---|---|---|
| X500 V2 PX4 Dev Kit (pick **Pixhawk 6C, 915 MHz**) | https://holybro.com/products/px4-development-kit-x500-v2 | ~$800–885 |
| PMW3901 optical flow (UART) | https://holybro.com/products/pmw3901-optical-flow-sensor | $20.59 |
| Benewake TFmini-S LiDAR | https://www.sparkfun.com/tfmini-s-micro-lidar-module.html (also [Amazon](https://www.amazon.com/Benewake-TFMINI-S-Micro-LIDAR-Module/dp/B07BJZ18RC)) | ~$40–50 |
| Raspberry Pi 5 (8 GB) | https://www.pishop.us/product/raspberry-pi-5-8gb/ (or [Adafruit](https://www.adafruit.com/product/5813), [CanaKit](https://www.canakit.com/raspberry-pi-5-8gb.html)) | $95 board / $120–180 kit |
| Arducam AR0234 global-shutter USB3 (with enclosure) | https://www.arducam.com/arducam-2-3mp-ar0234-color-global-shutter-usb-3-0-camera-module-with-enclosure.html (also [Amazon](https://www.amazon.com/Arducam-Global-Shutter-High-Speed-Windows/dp/B0DBV8VFJZ)) | ~$160–170 |
| RadioMaster Pocket (ELRS 2.4 GHz) | https://radiomasterrc.com/products/pocket-radio-controller-m2 (or [Rotor Riot](https://rotorriot.com/products/pocket-radio-controller-elrs)) | ~$78 (+18650 battery) |
| RadioMaster RP1 ELRS receiver | https://radiomasterrc.com/products/rp1-expresslrs-2-4ghz-nano-receiver (or [RMRC](https://www.readymaderc.com/products/details/radiomaster-rp1-elrs-24ghz-nano-receiver)) | ~$6 |
| 4S 5000 mAh LiPo (XT60), ×2 | https://www.amazon.com/HRB-5000mAh-Connector-Airplane-Helicopter/dp/B06XK8WWX1 | ~$50 ea |
| Hobbywing UBEC 5 A (2–8S) | https://www.hobbywingdirect.com/products/ubec-5a-air (or [Lumenier @ GetFPV](https://www.getfpv.com/lumenier-ubec-5v-5-5v-6v-5a-2-6s-input.html)) | ~$15 |
| LiPo balance charger (e.g. HOTA D6 Pro / ISDT) | [Amazon search](https://www.amazon.com/s?k=hota+d6+pro+lipo+charger) — any 2–6S balance charger | ~$70–90 |
| LED light bar, prop guards, mounts | [Holybro store](https://holybro.com/collections/x500-kits) accessories + [Amazon](https://www.amazon.com/s?k=drone+led+light+bar+5v) generic | ~$100 |

Notes: pick the **Pixhawk 6C + 915 MHz** kit variant (US ISM band). The Pocket TX
needs a flat-top 18650 cell (not included). Battery/charger links are commodity
items — any equivalent 4S XT60 pack / 2–6S balance charger works. LiPos often
ship ground-only.

---

## Smaller-airframe variant (chosen): Holybro QAV250 — half the footprint

The X500 is ~50 cm motor-to-motor (~70 cm with guards) — flyable in a standard
2.5–3.5 m aisle but big. The **QAV250 (250 mm wheelbase, ~35–40 cm with guards)**
runs the identical PX4 architecture at roughly half the size and ~40 % of the
weight (less downwash, less scary, easier to cage).

| Item | Link | ~USD |
|---|---|---|
| **Holybro QAV250 kit + Pixhawk 6C Mini** (frame, 2207 motors, ESCs, PM06 V2, no-solder; Basic version — GPS/VTX not needed) | https://holybro.com/products/qav250-kit | $408 (complete) / less for Basic |
| PMW3901 optical flow (UART) | https://holybro.com/products/pmw3901-optical-flow-sensor | $21 |
| TFmini-S downward LiDAR | [SparkFun](https://www.sparkfun.com/tfmini-s-micro-lidar-module.html) / [Amazon](https://www.amazon.com/Benewake-TFMINI-S-Micro-LIDAR-Module/dp/B07BJZ18RC) | $40–50 |
| Raspberry Pi 5 8 GB (heatsink only, no case — save weight) | [PiShop.us](https://www.pishop.us/product/raspberry-pi-5-8gb/) | $95 + $25 SD/cooler |
| Arducam AR0234 global-shutter USB3 (**bare board**, lighter) | https://www.arducam.com/arducam-2-3mp-ar0234-color-global-shutter-usb-3-0-camera-module-without-enclosure.html | ~$150 |
| RadioMaster Pocket + RP1 receiver | [Pocket](https://radiomasterrc.com/products/pocket-radio-controller-m2) · [RP1](https://radiomasterrc.com/products/rp1-expresslrs-2-4ghz-nano-receiver) | $84 |
| 4S 1500–2200 mAh LiPo ×3 (NOT 5000 — too heavy for 250 class) | [CNHL 4S 1500 2-pack](https://www.amazon.com/CNHL-Quadcopter-Helicopter-Airplane-Multi-Motor/dp/B07V1TYR3P) | ~$70 |
| Balance charger, UBEC 5 V/5 A, LED, 5" prop guards, mounts | see main table above | ~$150 |
| **Total** | | **~$1,050–1,250** |

Trade-offs vs the X500 build (all acceptable for the demo):
- **Flight time ~8–12 min** per pack (vs 15–20) — hence 3 batteries.
- **Cramped mounting** — the Pi 5 rides the top plate on standoffs; expect
  zip-tie engineering, and possibly one solder joint to tap 5 V for the UBEC
  from the PM06 (or use an XT30 Y-lead to stay solder-free).
- Payload margin is tighter but fine: 2207 racing motors on 4S lift the
  ~180 g Pi+camera+flow payload easily at demo speeds.
- Telemetry radio isn't in the QAV250 kit — skip it: the Pi bridges MAVLink to
  QGroundControl over Wi-Fi (cleaner anyway).
- PMW3901 min range is 8 cm — readings are invalid sitting on the ground;
  normal and handled once airborne.

### Alternative: DroneBlocks DEXI (integrated indoor PX4 dev drone)
- 368×328 mm carbon frame; **ARK Pi6X Flow** all-in-one board (FMUv6X FC +
  Pi CM4 + optical flow + ToF, NDAA/US-made), Pi camera, PX4 — literally this
  BOM pre-integrated. RTF kits include TX/RX/battery/charger.
- https://droneblocks.io/product/autonomous-drone-kit-level-iii-dexi-px4-rtf/
  (price not published — quote via DroneBlocks/Pitsco before comparing).
- Worth a quote if you'd rather not assemble; confirm it fits $2k.

Also in this size class: ModalAI **Starling 2** is only ~280 g and would be ideal
(VIO + avoidance) but is ~$2,950; COEX Clover (~$400–500, solderless, PX4+Pi+flow)
exists but US supply/support is spotty.

> **Skipped on purpose:** GPS module ships in the kit — leave it off/disabled
> (EKF2 configured for flow+range). No Marvelmind ($668 saved), no depth camera
> (no OA requirement), no Jetson (Pi 5 decodes 1–2 fps regions fine; it is not
> doing VIO).

## Barcode scanning + streaming (both, simultaneously)

- **Local decode (primary):** AR0234 → Pi 5 → `warehouse_scan` decode onboard →
  append `{barcode, placard/position, timestamp}` to local queue → publish JSON
  over Wi-Fi (MQTT/HTTP) to your laptop. Never decode from compressed video.
- **Live feed (demo visual):** Pi runs mediamtx (RTSP/WebRTC); stream a
  low-bitrate preview with decode overlays. Compression hurts *decoding*, not
  *watching* — so decode from raw frames onboard, stream the pretty picture.

## Honest limits (set demo expectations)

| Limit | Why | Mitigation |
|---|---|---|
| Flow accuracy drops above ~3 m | PMW3901 + floor-texture physics | Fly at 1.5–2.5 m; demo lower rack levels only |
| Polished/featureless concrete degrades flow | Mouse-sensor needs texture | Textured demo area, or add floor tape/mats; good light |
| Position drifts over minutes | Velocity integration, no absolute fix | Short missions; AprilTag placards to re-anchor |
| No obstacle avoidance | Not in scope/budget | Open area, slow speeds, prop guards, safety pilot |
| Rolling-shutter smear — solved | AR0234 is global shutter | Hover/creep during reads anyway |

## Build order (maps to docs/PLAN.md phases)

1. Bench: run `warehouse_scan benchmark` on photos of your real labels (free, today).
2. Assemble kit (~30 min) + flash PX4 v1.17; configure flow+range EKF2 params
   (`EKF2_OF_CTRL`, `EKF2_RNG_CTRL`, `EKF2_HGT_REF=Range`, GPS/mag off).
3. Manual hover on flow (caged) → confirm rock-solid Position-hold.
4. Pi 5: ROS 2 + uXRCE-DDS agent + offboard node — autonomous rectangle.
5. Add camera + decode service → hover at labels → JSON scans on your laptop.

## What carries over to the real system

Everything except the localization sensor: the airframe, Pi/ROS 2 offboard stack,
camera, decode pipeline, placard scheme, and ground-ingest flow all transfer.
Upgrading later = swap flow/LiDAR for VIO (VOXL/Starling class) for full-height
aisles + obstacle avoidance. This demo is a **subset of** the production design,
not a dead-end like the DJI path.
