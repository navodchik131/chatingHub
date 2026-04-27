from __future__ import annotations

import logging
import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import BACKEND_DIR
from app.db.models import StudioGeneration

log = logging.getLogger(__name__)

MAX_ARCHIVE_BYTES = 25 * 1024 * 1024


async def download_and_create_generation(
    session: AsyncSession,
    *,
    owner_id: int,
    source_url: str,
    refined_prompt: str,
    output_aspect: str | None,
    studio_model_id: int | None,
) -> StudioGeneration | None:
    """Скачивает картинку с WaveSpeed/CDN и сохраняет в data/studio_generations/…"""
    url = (source_url or "").strip()
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.content
    except Exception as e:
        log.warning("studio archive download failed: %s", e)
        return None
    if len(data) > MAX_ARCHIVE_BYTES:
        log.warning("studio archive: file too large (%s bytes)", len(data))
        return None

    ct_header = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
    if "png" in ct_header:
        ext, media = ".png", "image/png"
    elif "jpeg" in ct_header or "jpg" in ct_header:
        ext, media = ".jpg", "image/jpeg"
    elif "webp" in ct_header:
        ext, media = ".webp", "image/webp"
    elif "gif" in ct_header:
        ext, media = ".gif", "image/gif"
    else:
        ext, media = ".png", "image/png"

    rel = f"data/studio_generations/{owner_id}/{uuid.uuid4().hex}{ext}"
    path = (BACKEND_DIR / rel).resolve()
    try:
        path.relative_to(BACKEND_DIR.resolve())
    except ValueError:
        log.warning("studio archive: bad path")
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    excerpt = ((refined_prompt or "").strip()[:2000]) or None
    row = StudioGeneration(
        user_id=owner_id,
        relative_path=rel.replace("\\", "/"),
        content_type=media,
        output_aspect=output_aspect,
        studio_model_id=studio_model_id,
        prompt_excerpt=excerpt,
        source_url=(url[:2000] if url else None),
    )
    session.add(row)
    await session.flush()
    return row


def safe_delete_generation_file(relative_path: str) -> None:
    p = (BACKEND_DIR / relative_path).resolve()
    try:
        p.relative_to(BACKEND_DIR.resolve())
    except ValueError:
        return
    if p.is_file():
        p.unlink(missing_ok=True)
