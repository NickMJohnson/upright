"""Generate printable rack-bay location placards (QR + human-readable caption).

Each placard encodes LOC:<code> — the ingest pipeline recognizes the LOC:
prefix and uses it to location-tag subsequent inventory reads.

Usage:
    python scripts/make_placards.py A07-B12-L3 A07-B13-L1 ...
    python scripts/make_placards.py --csv locations.csv     # one code per line/first column

Output: placards/<code>.png — QR sized to print at ~15x15 cm (readable from
several meters by a 1080p drone stream).
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import qrcode
from caption_util import add_caption

OUT = Path("placards")
QR_MODULE_PX = 24  # big modules -> long-range readability


def make_placard(code: str) -> Path:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=QR_MODULE_PX,
        border=4,
    )
    qr.add_data(f"LOC:{code}")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    canvas = add_caption(
        img.get_image() if hasattr(img, "get_image") else img, code, font_px=96
    )

    OUT.mkdir(exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", code)  # codes may contain '/' etc.
    out = OUT / f"{safe}.png"
    canvas.save(out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("codes", nargs="*", help="location codes, e.g. A07-B12-L3")
    parser.add_argument("--csv", help="CSV/text file, one location code per row (first column)")
    args = parser.parse_args()

    codes = list(args.codes)
    if args.csv:
        with open(args.csv, newline="") as fh:
            for row in csv.reader(fh):
                if row and row[0].strip() and row[0].strip().lower() != "location":
                    codes.append(row[0].strip())
    if not codes:
        parser.print_help()
        return 2

    for code in codes:
        print(f"  {make_placard(code)}")
    print(f"\n{len(codes)} placard(s) in {OUT.resolve()}/ — print at ~15x15 cm or larger.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
