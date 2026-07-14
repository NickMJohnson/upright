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
    # 1D item labels
    make_code128("SKU-000123-A", "code128_sku")
    make_code128("TOOL-777", "code128_tool777")
    make_ean13("400638133393", "ean13_product")  # 12 digits; checksum auto-added
    # QR item labels with the SAME payloads — for symbology A/B tests
    # (reconcile keys on the decoded string, so these are interchangeable)
    make_qr("SKU-000123-A", "qr_sku")
    make_qr("TOOL-777", "qr_tool777")
    make_qr("4006381333931", "qr_ean")
    print(f"Wrote sample barcodes to {OUT.resolve()}/")
    for p in sorted(OUT.iterdir()):
        print("  ", p.name)
