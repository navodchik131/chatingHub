"""Файлы библиотеки референсов на диске."""

from __future__ import annotations

import uuid
from pathlib import Path

from app.config import BACKEND_DIR
from app.services.companion_media.storage import (
    _IMAGE_EXT,
    _MAX_BYTES,
    _VIDEO_EXT,
    _ext_for_mime,
    media_type_for_mime,
)

REF_ROOT = (BACKEND_DIR / "data" / "creator_references").resolve()
_STORAGE_PREFIX = "data/creator_references/"


def is_creator_reference_path(value: str | None) -> bool:
    rel = (value or "").strip().replace("\\", "/")
    return rel.startswith(_STORAGE_PREFIX)


def save_creator_reference_file(
    *,
    owner_id: int,
    raw: bytes,
    content_type: str | None,
    filename: str | None = None,
) -> tuple[str, str, str]:
    if not raw:
        raise ValueError("empty file")
    if len(raw) > _MAX_BYTES:
        raise ValueError("file too large")
    ext = _ext_for_mime(content_type, filename)
    if ext not in _IMAGE_EXT and ext not in _VIDEO_EXT:
        raise ValueError("unsupported media type")

    owner_dir = (REF_ROOT / str(int(owner_id))).resolve()
    if not str(owner_dir).startswith(str(REF_ROOT)):
        raise RuntimeError("invalid reference path")
    owner_dir.mkdir(parents=True, exist_ok=True)

    file_id = uuid.uuid4().hex[:16]
    rel = f"{_STORAGE_PREFIX}{int(owner_id)}/{file_id}{ext}"
    path = (BACKEND_DIR / rel).resolve()
    path.write_bytes(raw)
    mime = (content_type or "").strip() or (
        "video/mp4" if ext in _VIDEO_EXT else "image/jpeg"
    )
    return rel, mime, media_type_for_mime(mime, filename)


def resolve_creator_reference_file(owner_id: int, storage_path: str | None) -> Path | None:
    rel = (storage_path or "").strip().replace("\\", "/")
    if not is_creator_reference_path(rel):
        return None
    path = (BACKEND_DIR / rel).resolve()
    owner_base = (REF_ROOT / str(int(owner_id))).resolve()
    if not str(path).startswith(str(owner_base)) or not path.is_file():
        return None
    return path


def delete_creator_reference_file(storage_path: str | None) -> None:
    rel = (storage_path or "").strip().replace("\\", "/")
    if not is_creator_reference_path(rel):
        return
    path = (BACKEND_DIR / rel).resolve()
    if path.is_file() and str(path).startswith(str(REF_ROOT)):
        path.unlink(missing_ok=True)
