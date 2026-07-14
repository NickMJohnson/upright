# Bill of materials — PX4 + VIO (no beacons) indoor barcode-scanning drone

Approximate mid-2026 USD. This path drops Marvelmind's beacon infrastructure and
localizes with **onboard Visual-Inertial Odometry (VIO)** instead, fed into PX4
EKF2 like GPS. The VIO platforms below also provide **obstacle avoidance** from the
same camera array — which a Marvelmind build does not.

VIO drifts over distance; bound it (and get barcode→location mapping) with printed
**AprilTag/QR placards** on the rack bays.

---

## Option 1 — ModalAI Starling 2 (recommended: fastest, VIO + OA included)

Buy a complete dev drone that already solves the hard part (GPS-denied VIO +
collision prevention), then add the barcode payload.

| Item | Why | ~USD |
|---|---|---|
| ModalAI **Starling 2** (or Starling 2 Max) prebuilt dev drone | PX4 + qVIO + collision avoidance + nav camera array; flies indoors day one, 40+ min | $2,950 |
| Global-shutter barcode camera (Arducam AR0234, or a ModalAI hi-res add-on) | **Global shutter mandatory** for in-flight 1D barcode decode | $170 |
| Onboard LED light bar/ring | Dim warehouse aisles | $30 |
| Extra flight batteries (×2–3) | Iteration; confirm how many ship with it | $150 |
| RC transmitter (RadioMaster Pocket ELRS) + receiver | Safety-pilot override during bring-up | $95 |
| Mounting hardware, cables, printed placards | Integrate the barcode cam + reset VIO drift | $40 |
| Ground laptop + QGroundControl + ROS 2 | You likely have the laptop; software is free | $0 |
| **Total** | | **~$3,400–3,450** |

> The Starling already carries a global-shutter tracking cam for VIO and stereo for
> avoidance; the *added* camera here is a dedicated, well-lit, forward barcode imager.
> Confirm ModalAI's current camera bundles — you may be able to use an onboard port
> instead of a USB camera.

## Option 2 — VOXL 2 on your own X500 frame (more custom, cheaper brain)

The VOXL 2 board **is** the flight controller + companion + VIO + avoidance, so you
skip a separate Pixhawk. More assembly than Option 1.

| Item | ~USD |
|---|---|
| Holybro X500 V2 **ARF** kit (frame + motors + ESCs + props, **no** autopilot) | ~$300 |
| ModalAI VOXL 2 board | ~$1,270 |
| VOXL camera bundle (tracking for VIO + stereo for OA + hi-res for barcodes) | ~$400–600 |
| 4S LiPo ×3 + charger + UBEC | ~$245 |
| RC TX + RX, prop guards, LED, mounts/cables | ~$240 |
| **Total** | **~$2,450–2,700** + assembly/bring-up time |

## Option 3 — Modular Pixhawk + Jetson + RealSense (cheapest parts, most software work)

You build VIO **and** avoidance yourself. The research is blunt that GPS-denied
state estimation is **not turnkey** on this route — budget weeks of integration.

| Item | Why | ~USD |
|---|---|---|
| Holybro X500 V2 PX4 Dev Kit (Pixhawk 6C) | Drone + FC bundle | $760–890 |
| NVIDIA Jetson Orin Nano Super dev kit | Runs VIO (VINS-Fusion / OpenVINS / Isaac ROS cuVSLAM) + decode | $249 |
| Intel RealSense D435i (depth, for obstacle avoidance) | Depth perception → planner / PX4 Collision Prevention | $320 |
| Arducam AR0234 global-shutter camera (VIO + barcode) | Localization features + barcode reads | $170 |
| 4S LiPo ×3 + charger + UBEC | | ~$245 |
| RC TX + RX, prop guards, LED, mounts/cables | | ~$240 |
| **Total** | | **~$2,000–2,300** hardware + heavy software effort |

---

## How it works (data flow)

1. **Localization (VIO):** global-shutter cam features + IMU → odometry → PX4 EKF2
   via `VISION_POSITION_ESTIMATE` / `ODOMETRY` (uORB `vehicle_visual_odometry`).
   Params: `EKF2_EV_CTRL`, `EKF2_HGT_REF=Vision`; disable GPS/baro/mag indoors.
2. **Drift correction + location tags:** AprilTag/QR placards on each bay give
   absolute fixes (reset VIO drift) and tag each scan with `AISLE/BAY/LEVEL`.
3. **Obstacle avoidance:** depth/stereo cameras → local map → planner/Collision
   Prevention slows or reroutes. **On VOXL/Starling this is built in
   (`voxl-mapper` + collision prevention); on the modular build you add it.**
4. **Scanning:** barcode camera → companion → `warehouse_scan` decode → log
   `{barcode, placard-location, timestamp}`.

## Obstacle avoidance — capability by build

| Build | Localization | Obstacle avoidance |
|---|---|---|
| **Starling 2 / VOXL 2** | qVIO (built in) | **Built in** (voxl-mapper + collision prevention) |
| Modular Pixhawk + Jetson | VINS/OpenVINS/cuVSLAM (you integrate) | Add RealSense + planner (you integrate) |
| *(for contrast)* PX4 + Marvelmind | Marvelmind beacons | **None** unless you add a depth camera |
| *(for contrast)* DJI Mini 3 demo | DJI VPS + Marvelmind sticks | **None** (base Mini 3 has no sensors) |

## VIO vs. Marvelmind — pick by your building

| | PX4 + VIO | PX4 + Marvelmind |
|---|---|---|
| Position type | relative (drifts) | absolute (no drift) |
| Building infrastructure | **none** | beacons mounted, line-of-sight |
| Tall-racking aisles | works (vision); needs texture/light | ultrasound blocked/echoey, weak Z |
| Obstacle avoidance | yes (VOXL/Starling built-in) | not included |
| Heading/yaw indoors | from VIO (no magnetometer needed) | needs paired beacons |
| Hard part | VIO drift → fixed by placards | beacon coverage + LoS + Z |
| ~Cost to prototype | $3,400 (Starling) / $2,500 (VOXL DIY) | ~$2,200–2,500 |
| How the pros do it | ✅ (Corvus etc. use many-camera VIO/SLAM) | rare at warehouse scale |

## Recommendation

For a real warehouse, **VIO is the better long-term bet** — no ceiling
infrastructure, works in tall aisles, and it's how the commercial systems (Corvus,
etc.) actually do it. Start on **Starling 2 / VOXL 2** so VIO + avoidance are solved
for you; reserve the modular Jetson route only if you must own every layer. Use
Marvelmind only for a small, open, low-ceiling space where you want absolute
position fast. As always, de-risk for $0 first with `warehouse_scan benchmark` on
your real labels.
