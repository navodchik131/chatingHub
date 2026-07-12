"""Хранение обложек platform-донатов на диске."""

from __future__ import annotations

import uuid
from pathlib import Path

from app.config import BACKEND_DIR

COVER_ROOT = (BACKEND_DIR / "data" / "creator_donation_covers").resolve()
_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_COVER_BYTES = 5 * 1024 * 1024
_STORAGE_PREFIX = "data/creator_donation_covers/"


def is_stored_cover_path(value: str | None) -> bool:
    rel = (value or "").strip().replace("\\", "/")
    return rel.startswith(_STORAGE_PREFIX)


def _ext_for_mime(mime: str | None, filename: str | None = None) -> str:
    m = (mime or "").lower()
    if "png" in m:
        return ".png"
    if "webp" in m:
        return ".webp"
    if "gif" in m:
        return ".gif"
    if filename:
        suf = Path(filename).suffix.lower()
        if suf in _ALLOWED_EXT:
            return suf
    return ".jpg"


def save_creator_donation_cover(
    *,
    owner_id: int,
    link_id: int,
    raw: bytes,
    content_type: str | None,
    filename: str | None = None,
) -> str:
    if not raw:
        raise ValueError("empty file")
    if len(raw) > MAX_COVER_BYTES:
        raise ValueError("cover too large")
    ext = _ext_for_mime(content_type, filename)
    if ext not in _ALLOWED_EXT:
        raise ValueError("unsupported image type")

    owner_dir = (COVER_ROOT / str(int(owner_id))).resolve()
    if not str(owner_dir).startswith(str(COVER_ROOT)):
        raise RuntimeError("invalid cover path")
    owner_dir.mkdir(parents=True, exist_ok=True)

    file_id = uuid.uuid4().hex[:12]
    rel = f"{_STORAGE_PREFIX}{int(owner_id)}/{int(link_id)}_{file_id}{ext}"
    path = (BACKEND_DIR / rel).resolve()
    if not str(path).startswith(str(BACKEND_DIR.resolve())):
        raise RuntimeError("invalid cover path")
    path.write_bytes(raw)
    return rel


def resolve_creator_donation_cover(owner_id: int, storage_path: str | None) -> Path | None:
    rel = (storage_path or "").strip().replace("\\", "/")
    if not is_stored_cover_path(rel):
        return None
    path = (BACKEND_DIR / rel).resolve()
    owner_base = (COVER_ROOT / str(int(owner_id))).resolve()
    if not str(path).startswith(str(owner_base)) or not path.is_file():
        return None
    if path.suffix.lower() not in _ALLOWED_EXT:
        return None
    return path


def delete_creator_donation_cover_file(storage_path: str | None) -> None:
    rel = (storage_path or "").strip().replace("\\", "/")
    if not is_stored_cover_path(rel):
        return
    path = (BACKEND_DIR / rel).resolve()
    if path.is_file() and str(path).startswith(str(BACKEND_DIR.resolve())):
        path.unlink(missing_ok=True)
