"""Read-rate benchmark: how robust is barcode decoding to drone-flight conditions?

A flying drone degrades barcode imagery in four main ways. This harness simulates
each axis independently (holding the others at nominal) and reports the decode
success rate per level, so you can translate "I want to read labels from the air"
into concrete requirements:

  * scale      -> camera resolution / standoff distance (fewer pixels on the code)
  * rotation   -> approach angle / drone yaw relative to the label
  * blur       -> motion blur from flight speed + exposure time (global vs rolling shutter)
  * brightness -> warehouse lighting / need for an onboard LED

Run:
    python -m warehouse_scan benchmark sample_data
    python -m warehouse_scan benchmark sample_data --trials 3   # avg over jittered runs

Ground truth is established by decoding each clean image first; a degraded read
"passes" only if it returns the same data string.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .detector import decode_frame, iter_image_files

RESULTS = Path("results")

# One-axis-at-a-time sweeps. Nominal = first value of each axis.
SCALE_LEVELS = [1.0, 0.5, 0.33, 0.25, 0.18, 0.12]   # fraction of original pixels
ROTATION_LEVELS = [0, 5, 10, 20, 35, 50]            # degrees
BLUR_LEVELS = [0, 1, 2, 4, 7]                        # motion-blur kernel length (px)
BRIGHT_LEVELS = [1.0, 0.6, 0.4, 0.25, 0.12]         # brightness multiplier


def _scale(img: np.ndarray, f: float) -> np.ndarray:
    if f >= 0.999:
        return img
    h, w = img.shape[:2]
    return cv2.resize(img, (max(1, int(w * f)), max(1, int(h * f))),
                      interpolation=cv2.INTER_AREA)


def _rotate(img: np.ndarray, deg: float) -> np.ndarray:
    if deg == 0:
        return img
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    cos, sin = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    m[0, 2] += (nw - w) / 2
    m[1, 2] += (nh - h) / 2
    return cv2.warpAffine(img, m, (nw, nh), borderValue=(255, 255, 255))


def _motion_blur(img: np.ndarray, k: int) -> np.ndarray:
    if k <= 0:
        return img
    kernel = np.zeros((k, k), dtype=np.float32)
    kernel[k // 2, :] = 1.0 / k  # horizontal motion
    return cv2.filter2D(img, -1, kernel)


def _brightness(img: np.ndarray, f: float) -> np.ndarray:
    if f >= 0.999:
        return img
    return np.clip(img.astype(np.float32) * f, 0, 255).astype(np.uint8)


@dataclass
class AxisResult:
    axis: str
    level: float
    decoded: int
    total: int

    @property
    def rate(self) -> float:
        return self.decoded / self.total if self.total else 0.0


def _ground_truth(images: list[tuple[str, np.ndarray]]) -> dict[str, str]:
    truth: dict[str, str] = {}
    for name, img in images:
        dets = decode_frame(img, source=name)
        if dets:
            truth[name] = dets[0].data
    return truth


def _passes(img: np.ndarray, expected: str) -> bool:
    return any(d.data == expected for d in decode_frame(img))


def run_benchmark(folder: str, trials: int = 1) -> dict:
    images = list(iter_image_files(folder))
    if not images:
        raise FileNotFoundError(f"No images in {folder} (run scripts/make_test_barcodes.py)")
    truth = _ground_truth(images)
    usable = [(n, img) for n, img in images if n in truth]
    if not usable:
        raise RuntimeError("None of the source images decoded cleanly — bad fixtures.")

    axes = {
        "scale": (SCALE_LEVELS, _scale),
        "rotation": (ROTATION_LEVELS, _rotate),
        "blur": (BLUR_LEVELS, _motion_blur),
        "brightness": (BRIGHT_LEVELS, _brightness),
    }

    out: dict[str, list[AxisResult]] = {}
    for axis, (levels, fn) in axes.items():
        out[axis] = []
        for level in levels:
            decoded = total = 0
            for _ in range(trials):
                for name, img in usable:
                    total += 1
                    if _passes(fn(img, level), truth[name]):
                        decoded += 1
            out[axis].append(AxisResult(axis, level, decoded, total))

    # also report rendered code width in px at each scale to map to real optics
    widths = {f: int(np.mean([_scale(img, f).shape[1] for _, img in usable]))
              for f in SCALE_LEVELS}
    return {"results": out, "scale_widths_px": widths,
            "n_images": len(usable), "trials": trials}


def _print_report(data: dict) -> None:
    print(f"\nRead-rate benchmark — {data['n_images']} code(s), {data['trials']} trial(s)\n")
    for axis, rows in data["results"].items():
        print(f"  {axis}:")
        for r in rows:
            bar = "#" * int(round(r.rate * 20))
            extra = ""
            if axis == "scale":
                extra = f"  (~{data['scale_widths_px'][r.level]}px wide)"
            print(f"    {str(r.level):>5} : {r.rate*100:5.0f}%  {bar:<20}{extra}")
        print()
    print("Interpretation: the level where read-rate drops sharply is your design")
    print("limit. 'scale' px-width is the key number — it tells you the minimum")
    print("pixels-across-the-label your camera+standoff must deliver in flight.\n")


def main_benchmark(folder: str, trials: int = 1) -> int:
    data = run_benchmark(folder, trials)
    RESULTS.mkdir(exist_ok=True)
    serializable = {
        "n_images": data["n_images"],
        "trials": data["trials"],
        "scale_widths_px": {str(k): v for k, v in data["scale_widths_px"].items()},
        "results": {
            axis: [{"level": r.level, "rate": r.rate,
                    "decoded": r.decoded, "total": r.total} for r in rows]
            for axis, rows in data["results"].items()
        },
    }
    (RESULTS / "benchmark.json").write_text(json.dumps(serializable, indent=2))
    _print_report(data)
    print(f"Full data -> {RESULTS / 'benchmark.json'}")
    return 0
