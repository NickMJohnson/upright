"""Command-line entry point.

Usage:
    python -m warehouse_scan image  <path.png>
    python -m warehouse_scan dir    <folder>
    python -m warehouse_scan video  <path.mp4> [--stride N]
    python -m warehouse_scan webcam [--device 0]
    python -m warehouse_scan stream <url> [--no-display] [--stride N]
    python -m warehouse_scan benchmark <folder> [--trials N]
    python -m warehouse_scan ingest <scans.jsonl> [--db PATH] [--mission ID]
    python -m warehouse_scan reconcile --expected <expected.csv> [--db PATH] [--mission ID]

`stream` reads a live RTMP/RTSP/HTTP URL (e.g. a drone feed relayed through
mediamtx) and decodes continuously, logging unique reads to results/stream.jsonl.
`ingest` replays decoder JSONL into the SQLite scan store (placard-aware).
`reconcile` compares the store against a WMS expected-inventory CSV and writes
cycle_counts.csv + exceptions.csv.

Decoded codes are printed and written to results/scan.jsonl (one JSON per line).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

from .detector import (
    decode_frame,
    dedupe,
    iter_image_files,
    iter_video_frames,
)

RESULTS = Path("results")


def _emit(detections, writer) -> None:
    for d in detections:
        print(f"  [{d.symbology}] {d.data}  ({d.source})")
        writer.write(json.dumps(d.as_dict()) + "\n")


def _run_images(pairs, label: str) -> int:
    RESULTS.mkdir(exist_ok=True)
    found = []
    with (RESULTS / "scan.jsonl").open("w") as writer:
        for source, img in pairs:
            dets = decode_frame(img, source=source)
            if dets:
                _emit(dets, writer)
            found.extend(dets)
    unique = dedupe(found)
    print(f"\n{label}: {len(unique)} unique code(s) decoded "
          f"({len(found)} total reads). -> {RESULTS / 'scan.jsonl'}")
    return 0


def _run_live(
    src,
    log_name: str,
    display: bool = True,
    stride: int = 1,
    reconnect: bool = False,
    relog_s: float = 5.0,
) -> int:
    """Shared live-decode loop for webcam devices and RTMP/RTSP URLs.

    Every decode is written to results/<log_name> if that code hasn't been
    logged in the last `relog_s` seconds. Time-based re-logging (rather than
    once-per-session dedupe) matters: placard re-reads must reach the JSONL so
    ingest keeps the correct location context when a bay is revisited, and
    repeat sightings must be countable downstream.
    """
    import datetime
    import json as _json
    import time

    import numpy as np

    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        print(f"Could not open video source: {src}", file=sys.stderr)
        return 1
    RESULTS.mkdir(exist_ok=True)
    log_path = RESULTS / log_name
    print(f"Reading {src} — logging to {log_path}. "
          + ("Press 'q' in the window to quit." if display else "Ctrl-C to stop."))
    last_logged: dict[tuple[str, str], float] = {}
    idx = 0
    last_dets: list = []
    try:
        with log_path.open("a") as log:
            while True:
                ok, frame = cap.read()
                if not ok:
                    if not reconnect:
                        break
                    print("Stream ended or dropped; retrying in 2s...")
                    cap.release()
                    time.sleep(2)
                    cap = cv2.VideoCapture(src)
                    if not cap.isOpened():
                        print("Reconnect failed.", file=sys.stderr)
                        return 1
                    continue
                idx += 1
                if idx % stride == 0:
                    last_dets = decode_frame(frame, source=f"{src}#{idx}")
                    now = time.monotonic()
                    for d in last_dets:
                        key = (d.symbology, d.data)
                        first_time = key not in last_logged
                        if first_time or now - last_logged[key] >= relog_s:
                            last_logged[key] = now
                            ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
                            rec = d.as_dict()
                            rec["ts"] = ts
                            log.write(_json.dumps(rec) + "\n")
                            log.flush()
                            if first_time:
                                print(f"  [{d.symbology}] {d.data}  @{ts}")
                if display:
                    for d in last_dets:
                        if len(d.points) >= 4:
                            cv2.polylines(frame, [np.array(d.points)], True, (0, 255, 0), 2)
                            cv2.putText(frame, d.data, d.points[0],
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.imshow("warehouse_scan (q to quit)", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        if display:
            cv2.destroyAllWindows()
    print(f"\nSession: {len(last_logged)} unique code(s). Log: {log_path}")
    return 0


def _run_webcam(device: int) -> int:
    return _run_live(device, "webcam.jsonl", display=True, stride=1)


def _run_stream(url: str, display: bool = True, stride: int = 3) -> int:
    return _run_live(url, "stream.jsonl", display=display, stride=stride,
                     reconnect=True)


def _run_ingest(paths: list[str], db: str, mission: str, window: float) -> int:
    from .ingest import connect, ingest_jsonl, observations

    conn = connect(db)
    try:
        for p in paths:
            summary = ingest_jsonl(conn, p, mission_id=mission, placard_window_s=window)
            print(f"{p}: " + ", ".join(f"{k}={v}" for k, v in summary.items()))
        obs = observations(conn, mission)
        print(f"\nStore now has {len(obs)} unique (barcode, location) observation(s) "
              f"for mission '{mission}' -> {db}")
    finally:
        conn.close()
    return 0


def _run_reconcile(expected_csv: str, db: str, mission: str, out_dir: str,
                   min_sightings: int = 1) -> int:
    from pathlib import Path as _Path

    from .ingest import connect, observations, placard_locations, visited_locations
    from .reconcile import reconcile, summarize
    from .wms import FileExchangeAdapter

    if not _Path(db).exists():
        print(f"Scan store not found: {db} — run `ingest` first "
              "(or pass the right --db path).", file=sys.stderr)
        return 1
    adapter = FileExchangeAdapter(expected_csv, out_dir)
    expected = adapter.fetch_expected()
    conn = connect(db)
    try:
        obs = observations(conn, mission)
        visited = visited_locations(conn, mission)
        placards = placard_locations(conn, mission)
    finally:
        conn.close()
    verdicts = reconcile(expected, obs, visited, placard_seen=placards,
                         min_sightings=min_sightings)
    counts = summarize(verdicts)
    counts_path = adapter.push_counts(verdicts)
    exceptions_path = adapter.push_exceptions(verdicts)

    print(f"Expected rows: {len(expected)}, observations: {len(obs)}, "
          f"visited locations: {len(visited)}, min sightings: {min_sightings}")
    for verdict in ("match", "missing", "misplaced", "unexpected", "unverified"):
        print(f"  {verdict:<11} {counts.get(verdict, 0)}")
    if counts.get("low_confidence"):
        print(f"  low_confidence {counts['low_confidence']} "
              "(below sightings threshold; in cycle_counts.csv, not exceptions.csv)")
    print(f"\nCycle counts -> {counts_path}\nExceptions  -> {exceptions_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="warehouse_scan")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_img = sub.add_parser("image", help="decode a single image")
    p_img.add_argument("path")

    p_dir = sub.add_parser("dir", help="decode every image in a folder")
    p_dir.add_argument("path")

    p_vid = sub.add_parser("video", help="decode a video file")
    p_vid.add_argument("path")
    p_vid.add_argument("--stride", type=int, default=5,
                       help="decode every Nth frame (default 5)")

    p_cam = sub.add_parser("webcam", help="decode from a live camera")
    p_cam.add_argument("--device", type=int, default=0)

    p_stream = sub.add_parser("stream", help="decode a live RTMP/RTSP/HTTP stream")
    p_stream.add_argument("url")
    p_stream.add_argument("--no-display", action="store_true",
                          help="headless mode (no preview window)")
    p_stream.add_argument("--stride", type=int, default=3,
                          help="decode every Nth frame (default 3)")

    p_bench = sub.add_parser("benchmark",
                             help="measure decode read-rate vs drone-flight degradations")
    p_bench.add_argument("path")
    p_bench.add_argument("--trials", type=int, default=1)

    p_ing = sub.add_parser("ingest", help="load decoder JSONL into the scan store")
    p_ing.add_argument("paths", nargs="+")
    p_ing.add_argument("--db", default="results/scans.db")
    p_ing.add_argument("--mission", default="default")
    p_ing.add_argument("--window", type=float, default=10.0,
                       help="placard location context window, seconds (default 10)")

    p_rec = sub.add_parser("reconcile",
                           help="compare scan store vs expected inventory CSV")
    p_rec.add_argument("--expected", required=True,
                       help="CSV with location,barcode[,description] columns")
    p_rec.add_argument("--db", default="results/scans.db")
    p_rec.add_argument("--mission", default="default")
    p_rec.add_argument("--out", default="results")
    p_rec.add_argument("--min-sightings", type=int, default=1,
                       help="observations seen fewer times than this become "
                            "low_confidence instead of misplaced/unexpected "
                            "claims (default 1 = off; 2 filters one-off misreads)")

    args = parser.parse_args(argv)

    if args.cmd == "image":
        img = cv2.imread(args.path)
        if img is None:
            print(f"Could not read image: {args.path}", file=sys.stderr)
            return 1
        return _run_images([(args.path, img)], "Image")
    if args.cmd == "dir":
        return _run_images(iter_image_files(args.path), f"Folder {args.path}")
    if args.cmd == "video":
        return _run_images(iter_video_frames(args.path, stride=args.stride),
                           f"Video {args.path}")
    if args.cmd == "webcam":
        return _run_webcam(args.device)
    if args.cmd == "stream":
        return _run_stream(args.url, display=not args.no_display, stride=args.stride)
    if args.cmd == "benchmark":
        from .benchmark import main_benchmark
        return main_benchmark(args.path, trials=args.trials)
    if args.cmd == "ingest":
        return _run_ingest(args.paths, args.db, args.mission, args.window)
    if args.cmd == "reconcile":
        return _run_reconcile(args.expected, args.db, args.mission, args.out,
                              min_sightings=args.min_sightings)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
