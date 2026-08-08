"""Тесты auto eye-liveness inpaint."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from app.services.studio_eye_liveness import (
    build_eye_region_mask_png,
    inpaint_edit_is_full_frame,
    should_run_auto_eye_inpaint,
)


def _solid_jpeg(w: int, h: int, color: tuple[int, int, int] = (180, 140, 120)) -> bytes:
    im = Image.new("RGB", (w, h), color)
    draw = ImageDraw.Draw(im)
    # простое «лицо» для эвристики
    draw.ellipse((w // 4, h // 8, 3 * w // 4, h // 2), fill=(200, 160, 140))
    buf = BytesIO()
    im.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def test_should_run_skips_no_face_mode() -> None:
    assert not should_run_auto_eye_inpaint(
        enabled=True,
        studio_mode="no_face",
        face_in_frame=True,
    )


def test_should_run_skips_manual_inpaint_mask() -> None:
    assert not should_run_auto_eye_inpaint(
        enabled=True,
        manual_inpaint_mask=True,
        studio_mode="model",
        face_in_frame=True,
    )


def test_should_run_when_face_in_frame() -> None:
    assert should_run_auto_eye_inpaint(
        enabled=True,
        studio_mode="model",
        face_in_frame=True,
    )


def test_should_run_model_mode_without_analysis() -> None:
    assert should_run_auto_eye_inpaint(
        enabled=True,
        studio_mode="grok_compose",
        face_in_frame=None,
    )


def test_build_eye_region_mask_returns_png() -> None:
    raw = _solid_jpeg(640, 960)
    mask = build_eye_region_mask_png(raw)
    assert mask is not None
    m = Image.open(BytesIO(mask)).convert("L")
    assert m.size == (640, 960)
    assert m.getextrema()[1] > 32


def test_build_eye_region_mask_rejects_tiny() -> None:
    raw = _solid_jpeg(64, 64)
    assert build_eye_region_mask_png(raw) is None


def test_inpaint_edit_rejects_eye_crop() -> None:
    full = _solid_jpeg(720, 1280)
    crop_buf = BytesIO()
    Image.new("RGB", (256, 256), (120, 90, 80)).save(crop_buf, format="JPEG")
    crop = crop_buf.getvalue()
    assert not inpaint_edit_is_full_frame(full, crop)


def test_inpaint_edit_accepts_matching_size() -> None:
    full = _solid_jpeg(720, 1280)
    same_buf = BytesIO()
    Image.new("RGB", (720, 1280), (120, 90, 80)).save(same_buf, format="JPEG")
    same = same_buf.getvalue()
    assert inpaint_edit_is_full_frame(full, same)
