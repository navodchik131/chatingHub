"""Пути хранения медиа Stars Business (вне companion media)."""

from __future__ import annotations

from pathlib import Path

from app.config import BACKEND_DIR

STARS_BUSINESS_MEDIA_ROOT = BACKEND_DIR / "data" / "stars_business"


def owner_media_dir(owner_tg_user_id: int) -> Path:
    root = STARS_BUSINESS_MEDIA_ROOT / str(owner_tg_user_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def relative_media_path(owner_tg_user_id: int, filename: str) -> str:
    return f"stars_business/{owner_tg_user_id}/{filename}"


def absolute_media_path(relative: str) -> Path:
    """stars_business/… — под data/; медиатека — data/companion_media/… в заказе."""
    rel = (relative or "").strip().replace("\\", "/")
    if rel.startswith("data/"):
        return (BACKEND_DIR / rel).resolve()
    return (BACKEND_DIR / "data" / rel).resolve()
