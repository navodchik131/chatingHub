"""Обработка изображений для EXIF-бота (тот же пайплайн, что в студии)."""

from __future__ import annotations

import logging
from functools import partial
from io import BytesIO
from typing import Any

import anyio
from PIL import Image

from app.db.models import ExifBotProfile
from app.services.studio_ai_metadata_strip import (
    apply_analog_humanize_to_image_bytes,
    strip_ai_metadata_from_image_bytes,
)
from app.services.studio_exif_profile import (
    extract_phone_exif_profile,
    phone_exif_profile_to_json,
    resolve_phone_export_preset,
)
from app.services.studio_phone_export import apply_phone_export_to_jpeg

log = logging.getLogger(__name__)


def extract_reference_profile(
    image_bytes: bytes,
    *,
    filename: str | None = None,
) -> tuple[str, str]:
    """Парсит EXIF эталона; возвращает (json_blob, summary)."""
    from app.services.studio_exif_profile import phone_exif_profile_summary

    profile = extract_phone_exif_profile(image_bytes, filename=filename)
    blob = phone_exif_profile_to_json(profile)
    summary = phone_exif_profile_summary(profile) or "OK"
    return blob, summary


def _ensure_jpeg_bytes(data: bytes) -> bytes:
    """Конвертирует PNG/WebP в JPEG для piexif."""
    try:
        im = Image.open(BytesIO(data))
    except Exception as e:
        raise ValueError("Не удалось открыть изображение.") from e
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    buf = BytesIO()
    im.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _resolve_preset(profile: ExifBotProfile, *, selfie: bool) -> dict[str, Any] | None:
    return resolve_phone_export_preset(
        phone_exif_selfie_json=profile.phone_exif_selfie_json,
        phone_exif_main_json=profile.phone_exif_main_json,
        camera_preset_id=profile.camera_preset_id,
        selfie=selfie,
    )


def profile_is_ready(profile: ExifBotProfile) -> bool:
    has_ref = bool(profile.phone_exif_selfie_json or profile.phone_exif_main_json)
    has_preset = bool((profile.camera_preset_id or "").strip())
    return has_ref or has_preset


def process_image_sync(
    image_bytes: bytes,
    profile: ExifBotProfile,
    *,
    selfie: bool,
) -> bytes:
    preset = _resolve_preset(profile, selfie=selfie)
    if not preset:
        raise ValueError(
            "Профиль не настроен: загрузите эталоны с телефона или выберите модель."
        )

    ext = ".jpg"
    data = _ensure_jpeg_bytes(image_bytes)

    stripped, _ = strip_ai_metadata_from_image_bytes(data, ext=ext)
    data = stripped

    humanized, applied = apply_analog_humanize_to_image_bytes(data, ext=ext)
    if applied:
        data = humanized

    out = apply_phone_export_to_jpeg(
        data,
        preset=preset,
        selfie=selfie,
        export_lat=profile.export_lat,
        export_lon=profile.export_lon,
        skip_grain=applied,
    )
    if out is None:
        raise ValueError("Не удалось записать EXIF в файл.")
    return out


async def process_image(
    image_bytes: bytes,
    profile: ExifBotProfile,
    *,
    selfie: bool,
) -> bytes:
    return await anyio.to_thread.run_sync(
        partial(process_image_sync, image_bytes, profile, selfie=selfie)
    )


def guess_selfie_from_image(image_bytes: bytes) -> bool:
    """Эвристика: портретная ориентация → чаще фронталка."""
    try:
        im = Image.open(BytesIO(image_bytes))
        w, h = im.size
        return h >= w
    except Exception:
        return False
