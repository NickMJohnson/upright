# Bill of materials — PX4 + Marvelmind indoor barcode-scanning drone

Approximate mid-2026 USD. This is the "build-your-own on an open autopilot" path:
a Pixhawk/PX4 quadcopter that fuses Marvelmind position into EKF2 (like GPS) for
GPS-denied indoor flight, with a companion computer running the barcode/QR decode.

## A. Drone platform (airframe + flight controller + propulsion + power)

| Item | Why | ~USD |
|---|---|---|
| Holybro X500 V2 — **PX4 Development Kit** (Pixhawk 6C) | Bundles frame, 2216 motors, ESCs, 1045 props, Pixhawk 6C, GPS/compass module, PM02 power module, SiK telemetry radio — the cheapest way to a working PX4 drone | $760–890 |
| 4S LiPo 5000 mAh (×3) | Flight batteries; carry spares for iteration | $150 |
| LiPo balance charger (e.g. ISDT / HOTA) | If you don't already have one | $80 |
| UBEC 5 V / 5 A | Clean 5 V for the companion computer + camera off the main battery | $15 |
| Prop guards (X500) + spare props | **Mandatory indoors** near racking/people | $45 |
| **Subtotal A** | | **~$1,050–1,180** |

## B. Indoor positioning — Marvelmind

| Item | Why | ~USD |
|---|---|---|
| Marvelmind Starter Set (Super-MP, 3D, 915/868 MHz) | Modem + ~4 beacons; one becomes the mobile "hedgehog" on the drone, the rest are stationary anchors. 3D set gives a height (Z) estimate | $668 |
| UART cable (beacon → Pixhawk TELEM port) | Feeds Marvelmind position to PX4 EKF2 | $5–10 |
| *(Optional)* 2nd mobile beacon on the drone | **Paired beacons give heading/yaw** — important because the magnetometer is unreliable near steel racks | ~$120–150 |
| **Subtotal B** | | **~$675–830** |

> Coverage note: a 4-beacon starter set covers a *small* area (one bay/room). A real
> warehouse needs more stationary beacons + Marvelmind "submaps" — budget extra
> beacons (~$120–150 each) per zone. Ultrasonic is line-of-sight, so tall racking
> limits it (this is the reason VIO is the long-term play — see [BUILD.md](BUILD.md)).

## C. Scanning payload (the actual "read barcodes" part)

| Item | Why | ~USD |
|---|---|---|
| Raspberry Pi 5 (8 GB) | Companion computer: runs the `warehouse_scan` decoder, ROS 2, the uXRCE-DDS agent, AprilTag placard reads | $80 |
| Pi 5 NVMe HAT + 256 GB NVMe (or A2 microSD) + active cooler + case | Storage for captured imagery + cooling | $40 |
| Arducam AR0234 global-shutter USB3 camera (1920×1200) | **Global shutter is mandatory** — rolling shutter smears 1D barcodes in flight | $170 |
| Onboard LED light bar/ring | Warehouse aisles are dim/uneven | $30 |
| USB3 cable + camera mount | | $15 |
| **Subtotal C** | | **~$335** |

## D. Control, ground station, safety

| Item | Why | ~USD |
|---|---|---|
| RC transmitter (RadioMaster Pocket ELRS or similar) | Safety-pilot manual override — essential during bring-up | $70 |
| ELRS receiver | Pairs to the TX; wires to Pixhawk | $25 |
| Ground-station laptop + QGroundControl | Mission planning, params, MAVLink — **you likely have the laptop**; QGC is free | $0 (existing) |
| Mounting hardware, standoffs, cables, zip ties, XT60s | Integrating companion/camera/beacon onto the frame | $50 |
| **Subtotal D** | | **~$145** |

## E. Software (all free / open-source)

PX4 v1.17 · QGroundControl · ROS 2 Jazzy · Micro-XRCE-DDS-Agent · `px4_msgs`/`px4_ros_com`
· `apriltag_ros` · this repo's `warehouse_scan` decoder. **$0.**

## F. Consumables

| Item | ~USD |
|---|---|
| Printed AprilTag/QR **location placards** for rack bays (geo-tag each scan + bound drift) | ~$0 (print) |

---

## Totals

| Build | ~USD |
|---|---|
| **Core working prototype** (A + B + C + D, single-bay Marvelmind coverage) | **~$2,200–2,500** |
| + heading beacon (paired) | +$130 |
| + extra Marvelmind beacons per additional zone | +$120–150 each |

## Recommended optional upgrades

| Item | Instead of / in addition to | ~USD | When |
|---|---|---|---|
| NVIDIA Jetson Orin Nano Super dev kit | Raspberry Pi 5 | $249 (vs $80) | If you want GPU-accelerated AprilTag/VIO and a path to onboard VIO later |
| Optical-flow (ARK Flow / PMW3901) + downward LiDAR | — | $50–250 | Rock-solid Altitude/Position-hold as a safety layer independent of Marvelmind |
| Pixhawk 6X (vs 6C) | Pixhawk 6C in kit | +$150 | Redundant IMUs, more robust for serious flying |

## Key integration notes (so the BOM actually flies)

1. **Marvelmind → PX4:** mount one mobile beacon on the drone, wire it to a Pixhawk
   TELEM UART; it streams position that PX4 fuses via `VISION_POSITION_ESTIMATE` /
   `ODOMETRY` into EKF2. Set `EKF2_EV_CTRL`, `EKF2_HGT_REF=Vision`, disable
   GPS/baro/mag fusion indoors. (Marvelmind publishes a Holybro X500 + Pixhawk 6C +
   PX4 guide that walks this through.)
2. **Yaw is the hard part indoors** — the magnetometer is unreliable near steel
   racking. Use **two paired beacons** on the drone for heading, or a vision-based
   yaw source. Don't skip this; bad yaw = the drone flies off in the wrong direction.
3. **The companion computer does the scanning, not the Pixhawk:** camera → Pi 5 →
   `warehouse_scan` decode → log `{barcode, placard-location, timestamp}`. The Pi
   also runs the uXRCE-DDS agent so a ROS 2 mission node can command offboard flight.
4. **Coverage scales with beacons, not software** — the starter set is a single-zone
   demo. Plan beacon count + mounting for the real floor area before committing.

> Cross-checks: Marvelmind starter-set price is the link you found ($667.57).
> Drone/companion/camera prices are from this project's verified hardware research
> (mid-2026). Verify live prices before ordering; LiPo shipping has restrictions.
