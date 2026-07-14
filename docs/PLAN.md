# Roadmap

Goal: autonomous warehouse inventory scanning — drone reads barcodes, results
reconcile against the WMS. We get there in phases, each one shippable.

## Phase A — Piloted demo (current)

Human-flown DJI Mini 4 Pro streams RTMP to a laptop running the live decoder.
See [DEMO-RTMP.md](DEMO-RTMP.md).

- [x] Perception pipeline (decode images/video/webcam/stream) — verified
- [x] RTMP receive path (mediamtx + `stream` CLI) — verified with simulated feed
- [x] Read-rate benchmark harness (resolution/angle/blur/lighting)
- [ ] Benchmark on photos of the real warehouse labels
- [ ] Print location placard QRs for a few bays (location-tagged scans)
- [ ] Fly the demo: hover at 4–6 labels, show `results/stream.jsonl`
- [ ] Record 4K onboard; compare stream vs SD-card read-rates

**Success:** live decode of real labels in the warehouse, on video, in front of
stakeholders.

## Phase B — WMS integration (software, parallel to anything)

Scan records → ingest → dedupe → reconcile vs expected stock → cycle-count
feed + exceptions report. Full plan: [WMS-INTEGRATION.md](WMS-INTEGRATION.md).
Can be piloted with handheld scans before any autonomous flight.

## Phase C — Autonomous platform

PX4 QAV250 build (~$1.1–1.3k): optical flow + downward LiDAR for GPS/beacon-free
indoor position-hold, Pi 5 companion running onboard decode, offboard missions
via ROS 2. Parts: [BOM-vision-demo.md](BOM-vision-demo.md). Research/decisions:
[BUILD.md](BUILD.md).

1. PX4 SITL + Gazebo mission scripts (before hardware arrives)
2. Assemble, flow+LiDAR EKF2 bring-up, caged hover
3. Scripted aisle pass: hover at labels, decode onboard, placard-tagged records
4. Feed Phase-B pipeline from the drone instead of the pilot

## Phase D — Production decision gate

With demo + autonomy data in hand, decide:
- **Scale the build:** move to a VIO platform with obstacle avoidance
  ([BOM-px4-vio.md](BOM-px4-vio.md)) for full-height aisles and lights-out ops.
- **Or buy:** turnkey RaaS (Corvus Robotics, Gather AI, Verity) if coverage,
  reliability, and support economics beat building at scale.

## Platform decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06 | Skydio R1 ruled out | Discontinued; its Skills SDK no longer obtainable; no current Skydio path for custom onboard perception |
| 2026-06 | DJI + Marvelmind ruled out for autonomy | DJI FC is closed — no external position fusion; SDK virtual-stick control disables obstacle avoidance |
| 2026-06 | Marvelmind beacons deferred | Ultrasonic line-of-sight + weak Z don't scale to tall racking; PX4 fusion works but VIO/flow is infrastructure-free |
| 2026-06 | X500 swapped for QAV250 | 500 mm frame too large for aisles; 250 mm runs the identical PX4 stack |
| 2026-06 | Demo simplified to piloted Mini 4 Pro + RTMP | Proves scanning value now; autonomy proceeds in parallel as Phase C |
