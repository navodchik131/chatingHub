"""Watermark на бесплатных демо-генерациях."""

from __future__ import annotations

import logging
import math
from io import BytesIO

from app.config import settings

log = logging.getLogger(__name__)


def apply_demo_watermark(image_bytes: bytes, ext: str, media: str) -> tuple[bytes, str, str]:
    if not settings.demo_watermark_enabled:
        return image_bytes, ext, media
    if not image_bytes:
        return image_bytes, ext, media
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        log.warning("PIL not available; skip demo watermark")
        return image_bytes, ext, media

    label = (settings.demo_watermark_text or "ModelMate Demo").strip() or "ModelMate Demo"
    opacity = max(0.05, min(0.9, float(settings.demo_watermark_opacity)))
    alpha = int(round(255 * opacity))

    try:
        base = Image.open(BytesIO(image_bytes))
    except Exception:
        log.warning("demo watermark: cannot decode image")
        return image_bytes, ext, media

    rgba = base.convert("RGBA")
    width, height = rgba.size
    diag = math.hypot(width, height)
    font_size = max(28, int(diag * 0.06))
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    probe = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    pb = ImageDraw.Draw(probe).textbbox((0, 0), label, font=font)
    text_w = max(1, pb[2] - pb[0])
    text_h = max(1, pb[3] - pb[1])
    pad_x, pad_y = 48, 72
    tile_w = text_w + pad_x
    tile_h = text_h + pad_y

    tile = Image.new("RGBA", (tile_w, tile_h), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((pad_x // 2, pad_y // 2), label, font=font, fill=(255, 255, 255, alpha))
    tile = tile.rotate(-34, expand=True, resample=Image.Resampling.BICUBIC)

    overlay = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    step_x = max(1, int(tile.width * 0.72))
    step_y = max(1, int(tile.height * 0.72))
    for y in range(-tile.height, height + tile.height, step_y):
        for x in range(-tile.width, width + tile.width, step_x):
            overlay.alpha_composite(tile, (x, y))

    composed = Image.alpha_composite(rgba, overlay)
    out = BytesIO()
    if ext.lower() in (".jpg", ".jpeg") or media == "image/jpeg":
        composed.convert("RGB").save(out, format="JPEG", quality=92, optimize=True)
        return out.getvalue(), ".jpg", "image/jpeg"
    composed.save(out, format="PNG", optimize=True)
    return out.getvalue(), ".png", "image/png"
