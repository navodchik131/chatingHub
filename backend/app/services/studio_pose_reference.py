"""Временные файлы референса позы/кадра для WaveSpeed (HTTPS URL без загрузки в БД)."""

from __future__ import annotations

import uuid
from pathlib import Path

from app.config import BACKEND_DIR

POSE_REF_ROOT = (BACKEND_DIR / "data" / "studio_pose_refs").resolve()
_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def _ext_for_mime(mime: str | None) -> str:
    m = (mime or "").lower()
    if "png" in m:
        return ".png"
    if "webp" in m:
        return ".webp"
    return ".jpeg"


def save_pose_reference_bytes(*, owner_id: int, raw: bytes, content_type: str | None) -> str:
    """Сохраняет байты, возвращает file_id (без расширения) для JWT."""
    file_id = uuid.uuid4().hex
    ext = _ext_for_mime(content_type)
    owner_dir = (POSE_REF_ROOT / str(int(owner_id))).resolve()
    if not str(owner_dir).startswith(str(POSE_REF_ROOT)):
        raise RuntimeError("invalid pose ref path")
    owner_dir.mkdir(parents=True, exist_ok=True)
    path = owner_dir / f"{file_id}{ext}"
    path.write_bytes(raw)
    return file_id


def resolve_pose_reference_file(owner_id: int, file_id: str) -> Path | None:
    """Находит файл по stem=file_id в каталоге владельца."""
    root = POSE_REF_ROOT.resolve()
    base = (POSE_REF_ROOT / str(int(owner_id))).resolve()
    if not str(base).startswith(str(root)) or not base.is_dir():
        return None
    for p in base.glob(f"{file_id}.*"):
        if not p.is_file():
            continue
        rp = p.resolve()
        if not str(rp).startswith(str(base)):
            continue
        if p.suffix.lower() in _ALLOWED_EXT:
            return rp
    return None
