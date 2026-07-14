"""Shared helper: render a human-readable caption band under a code image."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
    except OSError:
        try:
            return ImageFont.load_default(size=size)  # Pillow >= 10.1
        except TypeError:
            return ImageFont.load_default()


def add_caption(img: Image.Image, text: str, font_px: int | None = None) -> Image.Image:
    """Return a new image with `text` centered in a white band below `img`."""
    img = img.convert("RGB")
    w, h = img.size
    font_px = font_px or max(20, w // 9)
    band = int(font_px * 1.5)
    canvas = Image.new("RGB", (w, h + band), "white")
    canvas.paste(img, (0, 0))
    draw = ImageDraw.Draw(canvas)
    font = _font(font_px)
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text(
        ((w - (bbox[2] - bbox[0])) / 2,
         h + (band - (bbox[3] - bbox[1])) / 2 - bbox[1]),
        text, fill="black", font=font,
    )
    return canvas
