"""Command-line entry point.

Usage:
    python -m warehouse_scan image  <path.png>
    python -m warehouse_scan dir    <folder>
    python -m warehouse_scan video  <path.mp4> [--stride N]
    python -m warehouse_scan webcam [--device 0]
    python -m warehouse_scan stream <url> [--no-display] [--stride N]
    python -m warehouse_scan benchmark <folder> [--trials N]

`stream` reads a live RTMP/RTSP/HTTP URL (e.g. a drone feed relayed through
mediamtx) and decodes continuously, logging unique reads to results/stream.jsonl.

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


def _run_webcam(device: int) -> int:
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        print(f"Could not open camera device {device}", file=sys.stderr)
        return 1
    print("Webcam scanning — press 'q' in the window to quit.")
    seen: set[tuple[str, str]] = set()
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            for d in decode_frame(frame, source="webcam"):
                key = (d.symbology, d.data)
                if key not in seen:
                    seen.add(key)
                    print(f"  [{d.symbology}] {d.data}")
                if len(d.points) >= 4:
                    import numpy as np
                    cv2.polylines(frame, [np.array(d.points)], True, (0, 255, 0), 2)
                    cv2.putText(frame, d.data, d.points[0],
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.imshow("warehouse_scan (q to quit)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
    print(f"\nWebcam session: {len(seen)} unique code(s) decoded.")
    return 0


def _run_stream(url: str, display: bool = True, stride: int = 3) -> int:
    import datetime
    import json as _json

    import numpy as np

    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print(f"Could not open stream: {url}\n"
              "Is mediamtx running and the source publishing?", file=sys.stderr)
        return 1
    RESULTS.mkdir(exist_ok=True)
    log_path = RESULTS / "stream.jsonl"
    print(f"Reading {url} — decoding every {stride} frame(s). Ctrl-C to stop.")
    seen: set[tuple[str, str]] = set()
    idx = 0
    last_dets: list = []
    try:
        with log_path.open("a") as log:
            while True:
                ok, frame = cap.read()
                if not ok:
                    print("Stream ended or dropped; retrying in 2s...")
                    cap.release()
                    cv2.waitKey(2000) if display else __import__("time").sleep(2)
                    cap = cv2.VideoCapture(url)
                    if not cap.isOpened():
                        print("Reconnect failed.", file=sys.stderr)
                        return 1
                    continue
                idx += 1
                if idx % stride == 0:
                    last_dets = decode_frame(frame, source=f"stream#{idx}")
                    for d in last_dets:
                        key = (d.symbology, d.data)
                        if key not in seen:
                            seen.add(key)
                            ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
                            print(f"  [{d.symbology}] {d.data}  @{ts}")
                            rec = d.as_dict()
                            rec["ts"] = ts
                            log.write(_json.dumps(rec) + "\n")
                            log.flush()
                if display:
                    for d in last_dets:
                        if len(d.points) >= 4:
                            cv2.polylines(frame, [np.array(d.points)], True, (0, 255, 0), 2)
                            cv2.putText(frame, d.data, d.points[0],
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.imshow("warehouse_scan stream (q to quit)", frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        if display:
            cv2.destroyAllWindows()
    print(f"\nStream session: {len(seen)} unique code(s). Log: {log_path}")
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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
