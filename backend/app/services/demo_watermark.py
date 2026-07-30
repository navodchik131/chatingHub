"""Watermark на бесплатных демо-генерациях."""

from __future__ import annotations

import logging
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
    try:
        base = Image.open(BytesIO(image_bytes))
    except Exception:
        log.warning("demo watermark: cannot decode image")
        return image_bytes, ext, media

    rgba = base.convert("RGBA")
    overlay = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = rgba.size
    font_size = max(18, min(width, height) // 28)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    text_bbox = draw.textbbox((0, 0), label, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    pad_x, pad_y = 14, 8
    box_w = text_w + pad_x * 2
    box_h = text_h + pad_y * 2
    x = max(12, width - box_w - 12)
    y = max(12, height - box_h - 12)
    draw.rounded_rectangle(
        (x, y, x + box_w, y + box_h),
        radius=8,
        fill=(8, 8, 10, 150),
    )
    draw.text((x + pad_x, y + pad_y), label, font=font, fill=(242, 243, 240, 230))

    # Диагональный полупрозрачный текст по центру
    diag_font_size = max(22, min(width, height) // 10)
    try:
        diag_font = ImageFont.truetype("arial.ttf", diag_font_size)
    except OSError:
        diag_font = font
    diag_layer = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    diag_draw = ImageDraw.Draw(diag_layer)
    diag_bbox = diag_draw.textbbox((0, 0), label, font=diag_font)
    diag_w = diag_bbox[2] - diag_bbox[0]
    diag_h = diag_bbox[3] - diag_bbox[1]
    diag_img = Image.new("RGBA", (diag_w + 20, diag_h + 20), (0, 0, 0, 0))
    ImageDraw.Draw(diag_img).text((10, 10), label, font=diag_font, fill=(255, 255, 255, 42))
    diag_img = diag_img.rotate(32, expand=True, resample=Image.Resampling.BICUBIC)
    dx = (width - diag_img.width) // 2
    dy = (height - diag_img.height) // 2
    overlay.alpha_composite(diag_img, (dx, dy))

    composed = Image.alpha_composite(rgba, overlay)
    out = BytesIO()
    if ext.lower() in (".jpg", ".jpeg") or media == "image/jpeg":
        composed.convert("RGB").save(out, format="JPEG", quality=92, optimize=True)
        return out.getvalue(), ".jpg", "image/jpeg"
    composed.save(out, format="PNG", optimize=True)
    return out.getvalue(), ".png", "image/png"
