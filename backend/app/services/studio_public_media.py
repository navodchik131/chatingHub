"""Локальное чтение файлов для public-* URL студии (без HTTP через nginx)."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BACKEND_DIR, settings
from app.db.models import StudioGeneration, UserStudioModel, UserStudioModelImage
from app.services.studio_generation_storage import generation_has_archive_file
from app.services.studio_image_token import (
    decode_generation_image_access_token,
    decode_model_image_access_token,
    decode_motion_video_access_token,
)
from app.services.studio_motion_video import resolve_motion_video_file


def _studio_public_url_paths(url: str) -> tuple[str, str] | None:
    """Возвращает (path, token) для наших public URL или None."""
    raw = (url or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    pub = (settings.public_app_url or "").strip().rstrip("/")
    if pub:
        pub_host = urlparse(pub if "://" in pub else f"https://{pub}").netloc.lower()
        if parsed.netloc and pub_host and parsed.netloc.lower() != pub_host:
            return None
    path = parsed.path.rstrip("/")
    if "/studio/public-" not in path:
        return None
    qs = parse_qs(parsed.query)
    tok = (qs.get("t") or [""])[0].strip()
    if not tok:
        return None
    return path, tok


async def read_studio_public_media_bytes(
    session: AsyncSession,
    url: str,
) -> bytes | None:
    """Читает байты с диска, если URL — наш JWT public endpoint."""
    parsed = _studio_public_url_paths(url)
    if not parsed:
        return None
    path, tok = parsed

    if path.endswith("/studio/public-generation-image"):
        try:
            uid, gid = decode_generation_image_access_token(tok)
        except ValueError:
            return None
        row = await session.get(StudioGeneration, gid)
        if not row or row.user_id != uid or not generation_has_archive_file(row):
            return None
        abs_path = (BACKEND_DIR / row.relative_path).resolve()
        try:
            abs_path.relative_to(BACKEND_DIR.resolve())
        except ValueError:
            return None
        if not abs_path.is_file():
            return None
        return abs_path.read_bytes()

    if path.endswith("/studio/public-model-image"):
        try:
            uid, iid = decode_model_image_access_token(tok)
        except ValueError:
            return None
        img = await session.get(UserStudioModelImage, iid)
        if not img:
            return None
        sm = await session.get(UserStudioModel, img.studio_model_id)
        if not sm or sm.user_id != uid:
            return None
        abs_path = (BACKEND_DIR / img.relative_path).resolve()
        try:
            abs_path.relative_to(BACKEND_DIR.resolve())
        except ValueError:
            return None
        if not abs_path.is_file():
            return None
        return abs_path.read_bytes()

    if path.endswith("/studio/public-motion-video"):
        try:
            uid, file_id = decode_motion_video_access_token(tok)
        except ValueError:
            return None
        vpath = resolve_motion_video_file(uid, file_id)
        if vpath is None or not vpath.is_file():
            return None
        return vpath.read_bytes()

    return None
