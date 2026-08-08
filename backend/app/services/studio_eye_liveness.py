"""Auto eye-liveness pass: маска области глаз + Z-Image inpaint после основной генерации."""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Any

import anyio
import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from app.config import settings
from app.services.studio_masked_regional_edit import (
    composite_fullframe_edit_preserving_unmasked,
    studio_mask_png_bytes_aligned_to_reference,
)
from app.services.wavespeed_client import (
    WaveSpeedImageResult,
    wavespeed_upload_image_bytes,
    z_image_turbo_inpaint_image_url,
)

log = logging.getLogger(__name__)

EYE_INPAINT_PROMPT = (
    "Edit only the white mask region. Refresh the eyes and immediate upper/lower eyelids only — "
    "keep iris color, brow shape, lashes, skin tone and face identity unchanged outside the mask. "
    "Make the gaze feel alive: asymmetric catchlights (main highlight offset slightly off-center), "
    "subtle natural squint or mid-blink softness, moist sclera with faint pink at inner corners, "
    "relaxed orbicular muscle — not a vacant doll stare, not glassy AI eyes, not enlarged anime iris. "
    "Photoreal phone snapshot micro-expression."
)


def should_run_auto_eye_inpaint(
    *,
    enabled: bool | None = None,
    manual_inpaint_mask: bool = False,
    studio_mode: str | None = None,
    face_in_frame: bool | None = None,
    include_face: bool | None = None,
    force: bool = False,
) -> bool:
    """Решает, нужен ли post-pass inpaint глаз."""
    if force:
        return bool(enabled if enabled is not None else settings.studio_eye_inpaint_enabled)
    on = settings.studio_eye_inpaint_enabled if enabled is None else enabled
    if not on or manual_inpaint_mask:
        return False
    mode = (studio_mode or "").strip().lower()
    if mode == "no_face":
        return False
    if face_in_frame is False or include_face is False:
        return False
    if face_in_frame is True or include_face is True:
        return True
    # Без анализа референса — для model/grok/bootstrap предполагаем лицо в кадре.
    if mode in ("model", "model_scene", "grok_compose", "photo_edit"):
        return True
    return False


def _draw_eye_ellipse(
    draw: ImageDraw.ImageDraw,
    *,
    cx: int,
    cy: int,
    rx: int,
    ry: int,
) -> None:
    draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)


def _mask_from_face_box(
    mask: Image.Image,
    *,
    x: int,
    y: int,
    fw: int,
    fh: int,
) -> bool:
    """Рисует пару эллипсов глаз в bbox лица."""
    w, h = mask.size
    eye_y = y + int(fh * 0.32)
    eye_h = max(4, int(fh * 0.11))
    eye_w = max(4, int(fw * 0.19))
    left_cx = x + int(fw * 0.28)
    right_cx = x + int(fw * 0.68)
    draw = ImageDraw.Draw(mask)
    _draw_eye_ellipse(draw, cx=left_cx, cy=eye_y, rx=eye_w, ry=eye_h)
    _draw_eye_ellipse(draw, cx=right_cx, cy=eye_y, rx=eye_w, ry=eye_h)
    # Расширяем область век — чуть шире эллипсы
    brow_y = max(0, eye_y - int(eye_h * 1.1))
    lid_y = min(h - 1, eye_y + int(eye_h * 1.35))
    for cx in (left_cx, right_cx):
        draw.ellipse(
            (cx - int(eye_w * 1.15), brow_y, cx + int(eye_w * 1.15), lid_y),
            fill=255,
        )
    return True


def _detect_face_box_cv2(rgb: np.ndarray) -> tuple[int, int, int, int] | None:
    try:
        import cv2
    except ImportError:
        return None
    try:
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)
        if cascade.empty():
            return None
        h, w = gray.shape[:2]
        min_side = max(48, int(min(w, h) * 0.08))
        faces = cascade.detectMultiScale(
            gray,
            scaleFactor=1.08,
            minNeighbors=4,
            minSize=(min_side, min_side),
        )
        if len(faces) == 0:
            return None
        x, y, fw, fh = max(faces, key=lambda f: int(f[2]) * int(f[3]))
        return int(x), int(y), int(fw), int(fh)
    except Exception as e:
        log.debug("cv2 face detect failed: %s", e)
        return None


def _heuristic_portrait_face_box(w: int, h: int) -> tuple[int, int, int, int]:
    """Fallback: типичное лицо в верхней центральной зоне портрета."""
    fw = int(w * 0.42)
    fh = int(h * 0.28)
    x = (w - fw) // 2
    y = int(h * 0.10)
    return x, y, fw, fh


def build_eye_region_mask_png(image_bytes: bytes) -> bytes | None:
    """
    PNG L-маска: белое = область глаз/век, чёрное = сохранить.
    None если кадр слишком мал или маска пустая.
    """
    if not image_bytes:
        return None
    im = ImageOps.exif_transpose(Image.open(BytesIO(image_bytes))).convert("RGB")
    w, h = im.size
    if min(w, h) < 128:
        return None

    mask = Image.new("L", (w, h), 0)
    rgb = np.asarray(im, dtype=np.uint8)
    box = _detect_face_box_cv2(rgb)
    if box is None:
        box = _heuristic_portrait_face_box(w, h)
    _mask_from_face_box(mask, x=box[0], y=box[1], fw=box[2], fh=box[3])

    if mask.getextrema()[1] < 16:
        return None

    # Мягкие края маски — inpaint меньше «режет» кожу
    mask = mask.filter(ImageFilter.GaussianBlur(radius=2.5))
    buf = BytesIO()
    mask.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _image_rgb_size(image_bytes: bytes) -> tuple[int, int]:
    im = ImageOps.exif_transpose(Image.open(BytesIO(image_bytes))).convert("RGB")
    return im.size


def inpaint_edit_is_full_frame(
    original_bytes: bytes,
    edited_bytes: bytes,
    *,
    min_side_ratio: float = 0.85,
    max_aspect_drift: float = 0.08,
) -> bool:
    """
    Z-Image иногда отдаёт только кроп маски (глаза), а не полный кадр.
    Такой результат нельзя подменять финальной генерации.
    """
    ow, oh = _image_rgb_size(original_bytes)
    ew, eh = _image_rgb_size(edited_bytes)
    if ow < 1 or oh < 1 or ew < 1 or eh < 1:
        return False
    if ew < ow * min_side_ratio or eh < oh * min_side_ratio:
        return False
    orig_ar = ow / oh
    edit_ar = ew / eh
    if abs(orig_ar - edit_ar) / max(orig_ar, 1e-6) > max_aspect_drift:
        return False
    return True


def blend_eye_inpaint_into_full_frame(
    original_bytes: bytes,
    edited_bytes: bytes,
    aligned_mask_bytes: bytes,
    *,
    feather_radius: float,
) -> bytes:
    """Вклеивает правку глаз обратно в исходный полный кадр."""
    return composite_fullframe_edit_preserving_unmasked(
        original_bytes,
        edited_bytes,
        aligned_mask_bytes,
        feather_radius=feather_radius,
    )


async def _download_image_bytes(url: str) -> bytes | None:
    u = (url or "").strip()
    if not u:
        return None
    timeout = float(settings.studio_archive_download_timeout_seconds)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(u)
            resp.raise_for_status()
            return resp.content or None
    except Exception as e:
        log.warning("eye inpaint download failed (%s): %s", u[:220], e)
        return None


async def apply_auto_eye_liveness_inpaint(
    *,
    api_key: str,
    source_image_url: str,
    prompt: str | None = None,
    feather_radius: float | None = None,
) -> WaveSpeedImageResult | None:
    """
    Скачивает кадр, строит маску глаз, вызывает Z-Image inpaint.
    При успехе возвращает результат; при ошибке — None (основной кадр не теряем).
    """
    src_url = (source_image_url or "").strip()
    if not src_url:
        return None

    raw = await _download_image_bytes(src_url)
    if not raw:
        return None

    mask_png = await anyio.to_thread.run_sync(build_eye_region_mask_png, raw)
    if not mask_png:
        log.info("eye inpaint skipped: no eye mask")
        return None

    aligned_mask = await anyio.to_thread.run_sync(
        studio_mask_png_bytes_aligned_to_reference,
        raw,
        mask_png,
    )

    try:
        img_ws_url = await wavespeed_upload_image_bytes(
            api_key=api_key,
            data=raw,
            filename="eye_inpaint_src.jpg",
            content_type="image/jpeg",
        )
        mask_ws_url = await wavespeed_upload_image_bytes(
            api_key=api_key,
            data=aligned_mask,
            filename="eye_inpaint_mask.png",
            content_type="image/png",
        )
    except Exception as e:
        log.warning("eye inpaint upload failed: %s", e)
        return None

    inpaint_prompt = (prompt or EYE_INPAINT_PROMPT).strip()
    size_inpaint: str | None = (
        None if settings.wavespeed_z_image_inpaint_omit_size else None
    )
    try:
        ws_res = await z_image_turbo_inpaint_image_url(
            api_key=api_key,
            image_url=img_ws_url,
            mask_image_url=mask_ws_url,
            prompt=inpaint_prompt,
            size=size_inpaint,
        )
    except Exception as e:
        log.warning("eye inpaint WaveSpeed failed: %s", e)
        return None

    out_url = (ws_res.url or "").strip()
    if not out_url:
        log.warning("eye inpaint: empty provider URL — keeping original")
        return None

    edited = await _download_image_bytes(out_url)
    if not edited:
        log.warning("eye inpaint: could not download provider output — keeping original")
        return None

    is_full_frame = await anyio.to_thread.run_sync(
        inpaint_edit_is_full_frame,
        raw,
        edited,
    )
    if not is_full_frame:
        ew, eh = await anyio.to_thread.run_sync(_image_rgb_size, edited)
        ow, oh = await anyio.to_thread.run_sync(_image_rgb_size, raw)
        log.warning(
            "eye inpaint: provider returned crop/wrong geometry edited=%sx%s original=%sx%s — keeping original",
            ew,
            eh,
            ow,
            oh,
        )
        return None

    feather = (
        settings.studio_eye_inpaint_blend_feather_radius
        if feather_radius is None
        else feather_radius
    )
    try:
        blended = await anyio.to_thread.run_sync(
            blend_eye_inpaint_into_full_frame,
            raw,
            edited,
            aligned_mask,
            feather_radius=max(float(feather), 0.0),
        )
        blended_url = await wavespeed_upload_image_bytes(
            api_key=api_key,
            data=blended,
            filename="eye_inpaint_out.jpg",
            content_type="image/jpeg",
        )
        return WaveSpeedImageResult(url=blended_url, task_id=ws_res.task_id)
    except Exception as e:
        log.warning("eye inpaint blend failed — keeping original: %s", e)
        return None


def eye_inpaint_billing_meta(applied: bool) -> dict[str, Any]:
    return {
        "eye_inpaint": applied,
        "eye_inpaint_enabled": settings.studio_eye_inpaint_enabled,
    }


async def maybe_apply_eye_liveness_postpass(
    *,
    api_key: str | None,
    source_image_url: str | None,
    manual_inpaint_mask: bool = False,
    studio_mode: str | None = None,
    face_in_frame: bool | None = None,
    include_face: bool | None = None,
    force: bool = False,
    prompt: str | None = None,
) -> tuple[str | None, bool]:
    """Возвращает (url, applied). При ошибке inpaint — исходный url, applied=False."""
    url = (source_image_url or "").strip() or None
    key = (api_key or "").strip()
    if not url or not key:
        return url, False
    if not should_run_auto_eye_inpaint(
        manual_inpaint_mask=manual_inpaint_mask,
        studio_mode=studio_mode,
        face_in_frame=face_in_frame,
        include_face=include_face,
        force=force,
    ):
        return url, False
    try:
        res = await apply_auto_eye_liveness_inpaint(
            api_key=key,
            source_image_url=url,
            prompt=prompt,
        )
    except Exception as e:
        log.warning("eye liveness postpass failed: %s", e, exc_info=True)
        return url, False
    if res and (res.url or "").strip():
        return res.url.strip(), True
    return url, False
