"""Хранение файлов медиатеки companion bot на диске."""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jose import JWTError, jwt

from app.config import BACKEND_DIR, settings

MEDIA_ROOT = (BACKEND_DIR / "data" / "companion_media").resolve()
_STORAGE_PREFIX = "data/companion_media/"

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_VIDEO_EXT = {".mp4", ".mov", ".webm"}
_MAX_BYTES = 50 * 1024 * 1024


def is_companion_media_path(value: str | None) -> bool:
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
    if "mp4" in m:
        return ".mp4"
    if "webm" in m:
        return ".webm"
    if "quicktime" in m or "mov" in m:
        return ".mov"
    if filename:
        suf = Path(filename).suffix.lower()
        if suf in _IMAGE_EXT or suf in _VIDEO_EXT:
            return suf
    return ".jpg"


def media_type_for_mime(mime: str | None, filename: str | None = None) -> str:
    ext = _ext_for_mime(mime, filename)
    if ext in _VIDEO_EXT:
        return "video"
    return "photo"


def save_companion_media_file(
    *,
    owner_id: int,
    studio_model_id: int,
    raw: bytes,
    content_type: str | None,
    filename: str | None = None,
) -> tuple[str, str, str]:
    """Сохраняет upload; возвращает (relative_path, content_type, media_type)."""
    if not raw:
        raise ValueError("empty file")
    if len(raw) > _MAX_BYTES:
        raise ValueError("file too large")

    ext = _ext_for_mime(content_type, filename)
    if ext not in _IMAGE_EXT and ext not in _VIDEO_EXT:
        raise ValueError("unsupported media type")

    owner_dir = (MEDIA_ROOT / str(int(owner_id)) / str(int(studio_model_id))).resolve()
    if not str(owner_dir).startswith(str(MEDIA_ROOT)):
        raise RuntimeError("invalid media path")
    owner_dir.mkdir(parents=True, exist_ok=True)

    file_id = uuid.uuid4().hex[:16]
    rel = f"{_STORAGE_PREFIX}{int(owner_id)}/{int(studio_model_id)}/{file_id}{ext}"
    path = (BACKEND_DIR / rel).resolve()
    if not str(path).startswith(str(BACKEND_DIR.resolve())):
        raise RuntimeError("invalid media path")
    path.write_bytes(raw)

    mime = (content_type or "").strip() or (
        "video/mp4" if ext in _VIDEO_EXT else "image/jpeg"
    )
    return rel, mime, media_type_for_mime(mime, filename)


def copy_studio_file_to_companion_media(
    *,
    owner_id: int,
    studio_model_id: int,
    source_relative_path: str,
    content_type: str | None,
) -> tuple[str, str, str]:
    """Копирует файл из архива студии в медиатеку companion."""
    src = (BACKEND_DIR / source_relative_path).resolve()
    if not src.is_file():
        raise ValueError("source file not found")
    if src.stat().st_size > _MAX_BYTES:
        raise ValueError("file too large")
    return save_companion_media_file(
        owner_id=owner_id,
        studio_model_id=studio_model_id,
        raw=src.read_bytes(),
        content_type=content_type,
        filename=src.name,
    )


def resolve_companion_media_file(owner_id: int, storage_path: str | None) -> Path | None:
    rel = (storage_path or "").strip().replace("\\", "/")
    if not is_companion_media_path(rel):
        return None
    path = (BACKEND_DIR / rel).resolve()
    owner_base = (MEDIA_ROOT / str(int(owner_id))).resolve()
    if not str(path).startswith(str(owner_base)) or not path.is_file():
        return None
    return path


def delete_companion_media_file(storage_path: str | None) -> None:
    rel = (storage_path or "").strip().replace("\\", "/")
    if not is_companion_media_path(rel):
        return
    path = (BACKEND_DIR / rel).resolve()
    if path.is_file() and str(path).startswith(str(MEDIA_ROOT)):
        path.unlink(missing_ok=True)


def create_companion_media_access_token(
    *, user_id: int, asset_id: int, days: int = 30
) -> str:
    """JWT для <img src> без Bearer — как у studio/chat media."""
    expire = datetime.now(timezone.utc) + timedelta(days=days)
    payload = {
        "typ": "companion_media",
        "uid": user_id,
        "aid": asset_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_companion_media_access_token(token: str) -> tuple[int, int]:
    try:
        data = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        raise ValueError("invalid token") from e
    if data.get("typ") != "companion_media":
        raise ValueError("wrong token type")
    uid = data.get("uid")
    aid = data.get("aid")
    if uid is None or aid is None:
        raise ValueError("missing claims")
    return int(uid), int(aid)
