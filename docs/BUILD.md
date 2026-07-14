# DIY build & platform decision: DJI+Marvelmind vs. build-your-own

> Scope note: the PX4/ROS 2, hardware, and indoor-localization facts here were
> verified via research (mid-2026). The DJI-specific deep dive was cut short by a
> billing limit, so DJI model/price specifics are from scouting + general
> knowledge — **verify current DJI SDK drone support before buying**.

## 1. The decision hinges on one fact: DJI's flight controller is closed

To fly autonomously with no GPS, *something* must continuously tell the aircraft
"where am I." There are two architecturally different ways to use an external
positioning source like Marvelmind:

- **Open autopilot (PX4 / ArduPilot on Pixhawk, or ModalAI VOXL):** the position
  estimate is fused **directly into the flight controller's state estimator**
  (PX4 EKF2 / ArduPilot EKF3) over MAVLink — exactly like GPS. The aircraft
  *truly knows where it is* and navigates on it. This is Marvelmind's documented,
  recommended path (they publish a Holybro X500 + Pixhawk 6C + PX4 guide).
- **DJI:** you **cannot inject an external position estimate into DJI's flight
  controller** — it's sealed. Marvelmind's DJI product works around this with a
  **Mobile SDK v5 app** that sends *waypoint / virtual-stick commands* computed
  from beacon position, while DJI's own visual positioning still stabilizes the
  aircraft. It's "piloting from the outside," not sensor fusion. Consequences:
  a limited supported-drone list, added latency, weaker control authority, and
  permanent dependence on DJI's SDK policy + geofencing. For Phantom/Mavic
  consumer models Marvelmind notes you can *track* but not autonomously fly
  without deeper hacking.

**Therefore Marvelmind really belongs to the build-your-own path.** Your real
choice is among the options below.

## 2. Decision matrix

| | **A. DJI + Marvelmind (MSDK)** | **B. Build: PX4 + Marvelmind** | **C. Build: PX4 + onboard VIO** ⭐ | **D. De-risk: Crazyflie + Lighthouse** |
|---|---|---|---|---|
| Positioning | Beacon → app → waypoint cmds (indirect) | Beacon → EKF2 (native) | Camera+IMU on-drone (VIO) → EKF2 | Base stations → onboard pose |
| Infra in the building | Ceiling/rack beacons + line-of-sight | Same beacon infra | **None** | 2 base stations (cage only) |
| Stack control | Low (closed) | Full | Full | Full |
| Warehouse fit | Limited drones; autonomy ceiling | Ultrasound blocked by tall racking; weak Z | **Best** (how Corvus etc. do it) | Toy/cage only, no payload |
| Barcode camera | Gimbal cam, off-board decode | Add global-shutter cam | Add global-shutter cam | N/A |
| Dev effort | Lower | Medium-high | High | Low |
| Rough cost to first prototype | ~$5–8k | ~$2–3k + beacons | ~$3–4k | ~$1k |
| Dead-end risk | Locked to DJI | Low | Low | It's a stepping stone |

⭐ = recommended target architecture.

## 3. Recommended architecture

**Build your own on PX4, localize with onboard VIO, and put fiducial location
placards (AprilTag/QR) on the rack bays.** The placards do double duty: they
bound VIO drift *and* they solve the barcode→AISLE/BAY/LEVEL problem (see §6).
Use Marvelmind only if your test space is small, open, and low-ceiling (§7).

Why VIO over Marvelmind for a real warehouse: Marvelmind is ultrasonic +
line-of-sight; tall racking and long canyon-like aisles block/echo the signal and
its **height (Z) axis is its weakest**, and it needs real mounted infrastructure.
VIO is infrastructure-free; its weakness (drift + repetitive-aisle aliasing) is
exactly what the rack placards fix.

## 4. Bill of materials (three tiers)

### Tier 0 — De-risk autonomy code in a cage (~$1,050)
| Item | ~USD |
|---|---|
| Crazyflie 2.1+ | $240 |
| Lighthouse Explorer bundle (2× V2 base stations + deck + Crazyradio) | $810 |

Flies in a ~5×5×2 m volume with <10 cm accuracy. No camera payload — this is for
proving your offboard/mission logic safely before flying a heavier drone.

### Tier 1 — Recommended: prebuilt VIO dev drone (~$3,200–3,600 + camera)
| Item | ~USD | Notes |
|---|---|---|
| ModalAI **Starling 2** (or Starling 2 Max) prebuilt dev drone | ~$2,950–3,000 | PX4 + qVIO + collision avoidance, flies indoors day one, 40+ min |
| Global-shutter barcode camera — Arducam AR0234 (1920×1200) | ~$170 | global shutter is **mandatory** for in-flight 1D barcode decode |
| Onboard LED illumination | ~$20–50 | warehouse aisles are dim/uneven |
| Spare batteries | ~$150 | |

Or buy the brain alone: **VOXL 2** board ~$1,270 (dev kit ~$1,370; usable VIO
config ~$1,600–1,900 w/ cameras) and mount it on your own airframe.

### Tier 2 — Modular, maximum flexibility (~$1,350–1,900 + integration time)
| Item | ~USD |
|---|---|
| Holybro X500 V2 PX4 dev kit (frame + motors/ESCs + Pixhawk + telemetry) | $760–890 |
| Pixhawk 6C ($166) or 6X ($320) — *included in kit, listed for reference* | — |
| NVIDIA Jetson Orin Nano Super dev kit (67 TOPS) | $249 |
| — or Jetson Orin NX 16GB (reComputer J4012, 157 TOPS) | $949 |
| Arducam AR0234 global-shutter USB camera | ~$170 |
| Prop guards, onboard LED, spares | ~$100 |

You integrate VIO/SLAM yourself (NVIDIA Isaac ROS cuVSLAM, VINS-Fusion, or
OpenVINS). Cheaper parts, but you take on the GPS-denied state-estimation work
that VOXL/Starling already solve.

### Cheapest stable-hover alternative to VIO
Optical-flow module (PMW3901 / ARK Flow) + a downward LiDAR rangefinder (~$50–250
total) gives rock-solid Altitude/Position-hold over a textured floor. It provides
*velocity, not absolute position* — pair it with rack placards (§6) for location.

## 5. Step-by-step build sequence

1. **Phase 1 — Perception on the bench (this repo, ~$0).** Photograph your real
   labels at realistic heights/distances/lighting and run
   `python -m warehouse_scan benchmark <folder>`. This sets your camera + standoff
   + flight-speed budget *before* you buy anything.
2. **Phase 2 — Autonomy logic in sim + cage.** PX4 SITL + Gazebo
   (`make px4_sitl gz_x500_mono_cam`); drive offboard missions over the
   uXRCE-DDS bridge from ROS 2. Then reproduce on Crazyflie + Lighthouse (Tier 0)
   in a netted area.
3. **Phase 3 — Real drone, GPS-denied hover.** On Starling 2 / VOXL 2, bring up
   qVIO → confirm stable indoor Position-hold (or optical-flow + LiDAR on the
   modular build). Tune EKF2 external-vision params (§9). Always caged, props
   guarded.
4. **Phase 4 — Aisle traversal + scan.** Fly a slow autonomous aisle pass; the
   forward global-shutter camera feeds `warehouse_scan.detector`; each decode is
   tagged with the nearest rack placard ID (§6). Write `{barcode, location,
   timestamp}` to a store.
5. **Phase 5 — WMS reconciliation.** Compare scans to expected inventory; flag
   mismatches; schedule recurring counts.

## 6. Tying a barcode to AISLE/BAY/LEVEL (the part people get wrong)

Do **not** trust raw drone pose at scan time — odometry drift + identical aisles
will file scans in the wrong bay. Most robust *and* cheapest: print a
**fiducial location placard** (AprilTag or QR encoding `AISLE/BAY/LEVEL`) on each
rack bay. When the camera sees a placard and a product barcode in the same pass,
the scan is geo-tagged by the *marker in frame*, not by drift-prone odometry. The
same placards also bound VIO drift (each unique tag is an absolute fix).
ROS 2 packages: `apriltag_ros`, or NVIDIA `isaac_ros_apriltag` on Jetson. Our
`warehouse_scan` detector already decodes QR placards today.

## 7. When Marvelmind *does* make sense, and what you'd need

Good for a **small, open, low-ceiling** test space where ultrasound has line of
sight (e.g., a single staging bay), as the fastest route to a stable indoor hover.
You'd need: a **Marvelmind Starter Set** (modem + ~4–5 stationary beacons + 1
mobile beacon/"hedgehog"; *approx* $500–900 — verify current pricing), mounted
with clear line-of-sight to the drone, wired to the Pixhawk over UART/USB, feeding
`VISION_POSITION_ESTIMATE` into EKF2. Expect weak Z/height accuracy and
significant mounting work as the space grows. It does **not** scale gracefully to
tall, full racking — that's where VIO + placards wins.

## 8. The DJI path — what you'd need, and its ceiling

If you insist on DJI: a **DJI enterprise drone** (consumer Mini/Air/Mavic are
"track-only" per Marvelmind) — realistically a **Mavic 3 Enterprise** (~$5k w/
controller) or a **Matrice** — plus Marvelmind's DJI Starter Set and their
**MSDK v5** Android app, and an onboard global-shutter view or off-board decode of
the gimbal footage. You get a polished camera and familiar hardware quickly, but
you hit a hard ceiling: no external-position fusion, limited supported drones,
no custom onboard autonomy, and you're subject to DJI policy/geofencing. Fine for
a quick demo; a poor base for a real, scalable inventory system.

## 9. Software versions & key params (verified mid-2026)

- **PX4** stable **v1.17.0** (prior v1.16.2). **ROS 2 Jazzy** (LTS, Ubuntu 24.04)
  recommended; Humble also supported. `px4_msgs`/`px4_ros_com` branch must match
  your PX4 release line; ROS 2 distro is independent.
- **Bridge:** uXRCE-DDS. Companion runs `MicroXRCEAgent udp4 -p 8888`
  (eProsima Micro-XRCE-DDS-Agent v2.4.3).
- **SITL:** modern Gazebo (gz-sim) Harmonic; `make px4_sitl gz_x500_mono_cam`
  (or `gz_x500_depth`).
- **Offboard:** stream `OffboardControlMode` + `TrajectorySetpoint` ≥2 Hz
  (examples use 10 Hz), switch mode + arm via `VehicleCommand`.
- **External vision → EKF2:** publish `VISION_POSITION_ESTIMATE` / `ODOMETRY`
  (uORB `vehicle_visual_odometry`) at 30–50 Hz. Params: `EKF2_EV_CTRL`,
  `EKF2_HGT_REF=Vision`, `EKF2_EV_DELAY`, `EKF2_EV_POS_X/Y/Z`; disable GNSS/mag
  indoors. Optical flow: `EKF2_OF_CTRL` (+ rangefinder `EKF2_RNG_CTRL`).
- **ArduPilot** alt: Copter 4.6.3 stable; native ROS 2 DDS (AP_DDS) on Humble;
  EKF3 + AP_VisualOdom; documented AprilTag-floor indoor workflow.

## 10. Bottom line + cheapest de-risk order

1. **Run the benchmark on your real labels (free).** If labels aren't readable
   from realistic drone distance, fix that (bigger labels / closer flight / better
   optics) before anything else.
2. **Prove autonomy on Crazyflie + Lighthouse (~$1k).**
3. **Buy a Starling 2 / VOXL 2 (~$3k)** and do GPS-denied hover → aisle scan with
   rack placards.
4. Reserve DJI+Marvelmind for a quick demo only; reserve Marvelmind-on-PX4 for
   small open spaces. **The scalable answer is PX4 + VIO + fiducial placards.**

Legal: a drone flown **entirely indoors** (enclosed, doors closed) is outside FAA
Part 107 — but property permission, building codes, and worker-safety practices
(prop guards, keep-out zones, fail-safe land) still apply.
