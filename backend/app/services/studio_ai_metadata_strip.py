"""Снятие C2PA / XMP / AI EXIF с кадров перед phone EXIF-подстановкой."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from app.config import settings

log = logging.getLogger(__name__)

_IMAGE_EXTS = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif", ".heif", ".heic", ".jxl"}
)


def _normalize_image_ext(ext: str) -> str:
    e = (ext or "").strip().lower()
    if not e.startswith("."):
        e = f".{e}" if e else ".png"
    if e == ".jpeg":
        return ".jpg"
    return e


def strip_ai_metadata_from_image_bytes(
    data: bytes,
    *,
    ext: str,
) -> tuple[bytes, bool]:
    """
    Убирает C2PA, XMP «Made with AI», AI EXIF и PNG text chunks провайдеров.
    Возвращает (байты, stripped). При ошибке или если метаданных нет — исходные байты.
    """
    if not settings.studio_strip_ai_metadata_enabled:
        return data, False
    if not data or len(data) < 32:
        return data, False

    norm_ext = _normalize_image_ext(ext)
    if norm_ext not in _IMAGE_EXTS:
        return data, False

    try:
        from remove_ai_watermarks.metadata import has_ai_metadata, remove_ai_metadata
    except ImportError:
        log.warning("remove-ai-watermarks not installed; skip AI metadata strip")
        return data, False

    src_path: Path | None = None
    out_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=norm_ext, delete=False) as src_f:
            src_f.write(data)
            src_path = Path(src_f.name)
        if not has_ai_metadata(src_path):
            return data, False
        with tempfile.NamedTemporaryFile(suffix=norm_ext, delete=False) as out_f:
            out_path = Path(out_f.name)
        remove_ai_metadata(src_path, out_path, keep_standard=True)
        cleaned = out_path.read_bytes()
        if cleaned and len(cleaned) <= 25 * 1024 * 1024:
            log.info("studio: stripped AI metadata (%s → %s bytes)", len(data), len(cleaned))
            return cleaned, True
        log.warning("studio: AI metadata strip produced empty or oversized output")
        return data, False
    except Exception as e:
        log.warning("studio: AI metadata strip failed: %s", e)
        return data, False
    finally:
        for p in (src_path, out_path):
            if p is not None:
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    pass


def _encode_cv_image(img, *, ext: str) -> bytes | None:
    import cv2

    norm = _normalize_image_ext(ext)
    if norm in (".jpg", ".jpeg"):
        ok, buf = cv2.imencode(
            ".jpg",
            img,
            [int(cv2.IMWRITE_JPEG_QUALITY), int(settings.studio_phone_export_jpeg_quality)],
        )
    elif norm == ".webp":
        ok, buf = cv2.imencode(".webp", img)
    else:
        ok, buf = cv2.imencode(".png", img)
    if not ok or buf is None:
        return None
    return buf.tobytes()


def apply_analog_humanize_to_image_bytes(
    data: bytes,
    *,
    ext: str,
) -> tuple[bytes, bool]:
    """
    Film grain + лёгкая хроматическая аберрация (remove-ai-watermarks humanizer).
    Возвращает (байты, applied). При ошибке — исходные байты.
    """
    if not settings.studio_analog_humanize_enabled:
        return data, False
    grain = float(settings.studio_analog_humanize_grain)
    if grain <= 0.0 and int(settings.studio_analog_humanize_chromatic_shift) <= 0:
        return data, False
    if not data or len(data) < 32:
        return data, False

    norm_ext = _normalize_image_ext(ext)
    if norm_ext not in _IMAGE_EXTS:
        return data, False

    try:
        import cv2
        import numpy as np
        from remove_ai_watermarks.humanizer import apply_analog_humanizer
    except ImportError:
        log.warning("remove-ai-watermarks/cv2 not available; skip analog humanize")
        return data, False

    try:
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return data, False
        out = apply_analog_humanizer(
            img,
            grain_intensity=grain,
            chromatic_shift=int(settings.studio_analog_humanize_chromatic_shift),
        )
        encoded = _encode_cv_image(out, ext=norm_ext)
        if encoded and len(encoded) <= 25 * 1024 * 1024:
            log.info("studio: analog humanize applied (%s bytes)", len(encoded))
            return encoded, True
        return data, False
    except Exception as e:
        log.warning("studio: analog humanize failed: %s", e)
        return data, False
