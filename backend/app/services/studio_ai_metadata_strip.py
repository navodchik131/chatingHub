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
