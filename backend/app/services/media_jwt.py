"""JWT для публичных медиа-URL — отдельный секрет от auth-сессии."""

from __future__ import annotations

from app.config import settings


def media_jwt_secret() -> str:
    custom = (settings.jwt_media_secret or "").strip()
    if custom:
        return custom
    return settings.jwt_secret
