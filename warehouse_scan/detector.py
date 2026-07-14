"""Core barcode/QR detection.

This is the drone-agnostic heart of the project: given image frames (from a
folder of photos, a video file, or a live camera), decode any 1D/2D barcodes in
them. pyzbar (libzbar) handles the common warehouse symbologies — Code128,
Code39, EAN/UPC, ITF, QR, DataMatrix-ish — and OpenCV's QRCodeDetector is used
as a second pass for QR codes pyzbar misses.
"""

from __future__ import annotations

import glob
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable, Iterator

import cv2
import numpy as np


def _ensure_zbar_on_path() -> None:
    """Make `from pyzbar import pyzbar` work on macOS without the user exporting
    DYLD_LIBRARY_PATH.

    pyzbar loads libzbar via ctypes.util.find_library, which on macOS only
    searches DYLD_(FALLBACK_)LIBRARY_PATH plus a few system dirs — Homebrew's
    /opt/homebrew/lib is NOT one of them. find_library reads the env var at call
    time, so prepending the brew zbar dir here (before the import below) is enough.
    """
    if sys.platform != "darwin":
        return
    for libdir in (
        "/opt/homebrew/opt/zbar/lib",  # Apple Silicon brew
        "/opt/homebrew/lib",
        "/usr/local/opt/zbar/lib",     # Intel brew
        "/usr/local/lib",
    ):
        if glob.glob(os.path.join(libdir, "libzbar*.dylib")):
            cur = os.environ.get("DYLD_LIBRARY_PATH", "")
            if libdir not in cur.split(":"):
                os.environ["DYLD_LIBRARY_PATH"] = f"{libdir}:{cur}" if cur else libdir
            return


_ensure_zbar_on_path()

try:
    from pyzbar import pyzbar  # type: ignore
    _HAVE_PYZBAR = True
except Exception:  # pragma: no cover - import guard for missing native lib
    pyzbar = None  # type: ignore
    _HAVE_PYZBAR = False


@dataclass
class Detection:
    """A single decoded code."""

    data: str
    symbology: str  # e.g. CODE128, EAN13, QRCODE
    points: list[tuple[int, int]] = field(default_factory=list)  # polygon corners
    source: str = ""  # file path or frame index it came from

    def as_dict(self) -> dict:
        return asdict(self)


def _preprocess(frame: np.ndarray) -> np.ndarray:
    """Grayscale + light contrast boost helps zbar on noisy/low-light frames
    (exactly the conditions a drone gives you under warehouse lighting)."""
    if frame.ndim == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)


def decode_frame(frame: np.ndarray, source: str = "") -> list[Detection]:
    """Decode all barcodes/QRs in a single BGR (or grayscale) frame."""
    detections: list[Detection] = []
    seen: set[tuple[str, str]] = set()
    gray = _preprocess(frame)

    if _HAVE_PYZBAR:
        for sym in pyzbar.decode(gray):
            try:
                data = sym.data.decode("utf-8", errors="replace")
            except Exception:
                data = repr(sym.data)
            key = (sym.type, data)
            if key in seen:
                continue
            seen.add(key)
            detections.append(
                Detection(
                    data=data,
                    symbology=sym.type,
                    points=[(p.x, p.y) for p in sym.polygon],
                    source=source,
                )
            )

    # OpenCV QR fallback (catches some QRs zbar misses; ignored if it finds none)
    try:
        qr = cv2.QRCodeDetector()
        ok, infos, pts, _ = qr.detectAndDecodeMulti(gray)
        if ok and pts is not None:
            for text, quad in zip(infos, pts):
                if not text:
                    continue
                key = ("QRCODE", text)
                if key in seen:
                    continue
                seen.add(key)
                detections.append(
                    Detection(
                        data=text,
                        symbology="QRCODE",
                        points=[(int(x), int(y)) for x, y in quad],
                        source=source,
                    )
                )
    except cv2.error:
        pass

    return detections


def iter_image_files(folder: str | Path) -> Iterator[tuple[str, np.ndarray]]:
    exts = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
    for p in sorted(Path(folder).iterdir()):
        if p.suffix.lower() in exts:
            img = cv2.imread(str(p))
            if img is not None:
                yield str(p), img


def iter_video_frames(path: str | Path, stride: int = 1) -> Iterator[tuple[str, np.ndarray]]:
    """Yield every `stride`-th frame from a video file (or device index as str)."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video source: {path}")
    idx = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % stride == 0:
                yield f"{path}#frame{idx}", frame
            idx += 1
    finally:
        cap.release()


def dedupe(detections: Iterable[Detection]) -> list[Detection]:
    """Collapse repeat reads of the same (symbology, data) across many frames —
    a drone will see the same label in dozens of consecutive frames."""
    out: list[Detection] = []
    seen: set[tuple[str, str]] = set()
    for d in detections:
        key = (d.symbology, d.data)
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out
