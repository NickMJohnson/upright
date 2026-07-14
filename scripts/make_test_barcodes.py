"""Generate sample barcodes/QRs so you can test the pipeline with no hardware.

Writes a Code128, an EAN-13, and a QR code into sample_data/, then you can run:
    python -m warehouse_scan dir sample_data
"""

from __future__ import annotations

from pathlib import Path

OUT = Path("sample_data")
OUT.mkdir(exist_ok=True)


def make_code128(value: str, name: str) -> None:
    import barcode
    from barcode.writer import ImageWriter

    code = barcode.get("code128", value, writer=ImageWriter())
    code.save(str(OUT / name))  # appends .png


def make_ean13(value: str, name: str) -> None:
    import barcode
    from barcode.writer import ImageWriter

    code = barcode.get("ean13", value, writer=ImageWriter())
    code.save(str(OUT / name))


def make_qr(value: str, name: str) -> None:
    import qrcode

    img = qrcode.make(value)
    img.save(str(OUT / f"{name}.png"))


if __name__ == "__main__":
    make_code128("SKU-000123-A", "code128_sku")
    make_ean13("400638133393", "ean13_product")  # 12 digits; checksum auto-added
    make_qr("LOC:AISLE-07/BAY-12/LEVEL-3", "qr_location")
    print(f"Wrote sample barcodes to {OUT.resolve()}/")
    for p in sorted(OUT.iterdir()):
        print("  ", p.name)
