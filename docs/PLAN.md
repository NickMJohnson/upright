# Plan: autonomous warehouse barcode scanning

## 0. The premise check (why not the Skydio R1)

| Question | Answer |
|---|---|
| Is there an R1 SDK to install? | **No.** The R1 Skills SDK (2018, Python, invite-only) is discontinued; only stale community forks remain. |
| Is the R1 fit for indoor warehouse barcode scanning? | **No.** It's a discontinued outdoor cinematic drone — not built for GPS-denied aisle flight or close-range barcode optics. |
| Can current Skydio run a custom onboard "barcode skill"? | **No.** Today's Skydio Extend = Cloud API + (gated) real-time ICD. No public onboard-perception SDK. |
| Is "fly + read barcodes" feasible at all? | **Yes** — Corvus, Gather AI, Verity ship it. Hard part is autonomy/optics, not decoding. |

## 1. Three realistic paths

### Path A — Buy a turnkey RaaS system  ✅ recommended for a working warehouse
- **Vendors:** Corvus Robotics (Corvus One — lights-out, no beacons, industrial
  barcode scanner, cold-chain variant), Gather AI (commodity drones + AI vision),
  Verity.
- **Model:** Robot-as-a-Service subscription. Vendor owns/maintains drones, free
  hardware/software upgrades, ~1–2 week deployment, integrates with your WMS.
- **Effort:** procurement + WMS integration. **Not** a drone-software build.
- **When:** you want inventory accuracy in production, not a research project.

### Path B — Build DIY on an open platform  🔬 if this is R&D / you must own the stack
- **Flight stack:** PX4 or ArduPilot. **App layer:** ROS 2.
- **Hardware:**
  - ModalAI **VOXL 2** — most integrated (autopilot + NVIDIA-class compute + cameras).
  - Modular: Holybro X500 + Pixhawk + NVIDIA Jetson companion + global-shutter cam.
  - Crazyflie + Lighthouse — safe, caged early prototyping.
- **Indoor localization (GPS-denied):** VIO / optical-flow / LiDAR-SLAM; optional
  UWB or fiducial/aisle markers.
- **Perception:** **this repo** (pyzbar/ZBar, OpenCV, ZXing, AprilTag).
- **Sim first:** PX4 SITL + Gazebo before any real flight.
- **Effort:** serious multi-person robotics R&D. The barcode part is the *easy* 10%.

### Path C — Force-fit Skydio enterprise  ⚠️ only if you're committed to Skydio
- Buy **X10** (enterprise) or **X10D** (defense/Blue UAS, ~$17–21k/unit).
- Use **3D Scan Indoor Capture** for autonomous GPS-denied missions.
- Use the **public Cloud API** (`warehouse_scan/skydio_cloud.py`) to pull captured
  media, then run **this repo's detector** off-board.
- Limits: no onboard barcode skill; barcode read quality depends on capture
  resolution/standoff; real-time control needs the gated X10D ICD. Skydio is not
  optimized for tight-aisle inventory the way Corvus/Gather are.

## 2. Phased roadmap (build/prototype track)

**Phase 1 — Perception on the bench (this repo, days).**
Prove decode reliability on photos/video of *your actual labels* under warehouse-like
lighting and distance. Measure read rate vs. distance, angle, motion blur, lighting.
This de-risks the whole project cheaply. → `python -m warehouse_scan ...`

**Phase 2 — Capture realism (1–2 weeks).**
Walk the aisles with a phone/gimbal cam (or a tethered drone) recording video at the
heights/standoffs a drone would fly. Run the detector over it. If read rate is poor,
you've learned you need closer flight, better optics/lighting, or fiducials — *before*
buying drones.

**Phase 3 — Localization + mapping (research, weeks–months for Path B).**
Decide how a code maps to a location: drone pose (VIO/SLAM) + aisle/bay fiducials, or
QR location tags on racks. Stand up PX4 SITL + Gazebo; fly a sim mission.

**Phase 4 — Closed-loop on hardware (Path B/C).**
Small dev drone in a caged area: autonomous aisle traverse → capture → decode →
write `{barcode, location, timestamp}` to a store. Then WMS reconciliation.

**Phase 5 — WMS integration & ops.**
Reconcile scans against expected inventory; flag mismatches; schedule recurring
counts. (Turnkey vendors give you this out of the box — Path A.)

## 3. Decision shortcut
- **Need inventory accuracy in a real warehouse now →** Path A (buy).
- **Building a product / research, want to own the stack →** Path B (PX4/ROS2/VOXL).
- **Org is standardized on Skydio →** Path C (X10 + Cloud API + this repo).

In every case, **Phase 1 of this repo is the right first move** — it costs nothing
and tells you whether your labels are even readable from the air.
