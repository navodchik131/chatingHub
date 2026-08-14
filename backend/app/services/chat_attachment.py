"""Вложения чата: хранение на диске и JWT для <img src>."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jose import JWTError, jwt

from app.config import BACKEND_DIR, settings

CHAT_MEDIA_ROOT = (BACKEND_DIR / "data" / "chat_media").resolve()
_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4"}
MAX_CHAT_IMAGE_BYTES = 10 * 1024 * 1024
MAX_CHAT_VIDEO_BYTES = 16 * 1024 * 1024


def _ext_for_mime(mime: str | None) -> str:
    m = (mime or "").lower()
    if "png" in m:
        return ".png"
    if "webp" in m:
        return ".webp"
    if "gif" in m:
        return ".gif"
    if "mp4" in m or m.startswith("video/"):
        return ".mp4"
    return ".jpeg"


def save_chat_media_bytes(*, owner_id: int, raw: bytes, content_type: str | None) -> tuple[str, str]:
    mime = (content_type or "image/jpeg").split(";")[0].strip().lower() or "image/jpeg"
    limit = MAX_CHAT_VIDEO_BYTES if mime.startswith("video/") else MAX_CHAT_IMAGE_BYTES
    if len(raw) > limit:
        raise ValueError(
            f"Файл слишком большой (макс. {limit // (1024 * 1024)} МБ)"
        )
    if not raw:
        raise ValueError("Пустой файл")
    file_id = uuid.uuid4().hex
    ext = _ext_for_mime(mime)
    owner_dir = (CHAT_MEDIA_ROOT / str(int(owner_id))).resolve()
    if not str(owner_dir).startswith(str(CHAT_MEDIA_ROOT)):
        raise RuntimeError("invalid chat media path")
    owner_dir.mkdir(parents=True, exist_ok=True)
    rel = f"data/chat_media/{int(owner_id)}/{file_id}{ext}"
    path = (BACKEND_DIR / rel).resolve()
    if not str(path).startswith(str(BACKEND_DIR.resolve())):
        raise RuntimeError("invalid chat media path")
    path.write_bytes(raw)
    return rel, mime


def save_chat_image_bytes(*, owner_id: int, raw: bytes, content_type: str | None) -> tuple[str, str]:
    return save_chat_media_bytes(owner_id=owner_id, raw=raw, content_type=content_type)


def resolve_chat_attachment_file(owner_id: int, relative_path: str) -> Path | None:
    root = CHAT_MEDIA_ROOT.resolve()
    rel = (relative_path or "").strip().replace("\\", "/")
    if not rel.startswith("data/chat_media/"):
        return None
    path = (BACKEND_DIR / rel).resolve()
    owner_base = (CHAT_MEDIA_ROOT / str(int(owner_id))).resolve()
    if not str(path).startswith(str(owner_base)) or not path.is_file():
        return None
    if path.suffix.lower() not in _ALLOWED_EXT:
        return None
    return path


def create_chat_attachment_access_token(
    *, user_id: int, attachment_id: int, days: int = 30
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=days)
    payload = {
        "typ": "chat_att",
        "uid": user_id,
        "aid": attachment_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_chat_attachment_access_token(token: str) -> tuple[int, int]:
    try:
        data = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        raise ValueError("invalid token") from e
    if data.get("typ") != "chat_att":
        raise ValueError("wrong token type")
    uid = data.get("uid")
    aid = data.get("aid")
    if uid is None or aid is None:
        raise ValueError("missing claims")
    return int(uid), int(aid)


def create_chat_media_public_token(
    *, owner_id: int, relative_path: str, hours: int = 24
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=hours)
    payload = {
        "typ": "chat_media_pub",
        "uid": owner_id,
        "rel": relative_path,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_chat_media_public_token(token: str) -> tuple[int, str]:
    try:
        data = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        raise ValueError("invalid token") from e
    if data.get("typ") != "chat_media_pub":
        raise ValueError("wrong token type")
    uid = data.get("uid")
    rel = data.get("rel")
    if uid is None or not rel:
        raise ValueError("missing claims")
    return int(uid), str(rel)


def chat_media_public_absolute_url(*, owner_id: int, relative_path: str) -> str:
    from app.config import settings

    tok = create_chat_media_public_token(owner_id=owner_id, relative_path=relative_path)
    base = (settings.public_app_url or "").strip().rstrip("/")
    return f"{base}/api/chat/media-public?t={tok}"


def create_conversation_avatar_access_token(
    *, owner_id: int, conversation_id: int, days: int = 7
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=days)
    payload = {
        "typ": "conv_avatar",
        "uid": owner_id,
        "cid": conversation_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_conversation_avatar_access_token(token: str) -> tuple[int, int]:
    try:
        data = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as e:
        raise ValueError("invalid token") from e
    if data.get("typ") != "conv_avatar":
        raise ValueError("wrong token type")
    uid = data.get("uid")
    cid = data.get("cid")
    if uid is None or cid is None:
        raise ValueError("missing claims")
    return int(uid), int(cid)


def conversation_avatar_url(*, owner_id: int, conversation_id: int) -> str:
    tok = create_conversation_avatar_access_token(
        owner_id=owner_id, conversation_id=conversation_id
    )
    return f"/api/conversations/{conversation_id}/avatar?t={tok}"
