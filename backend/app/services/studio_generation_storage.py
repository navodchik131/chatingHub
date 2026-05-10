from __future__ import annotations

import logging
import uuid
from functools import partial

import anyio
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import BACKEND_DIR
from app.db.models import StudioGeneration, UserStudioModel
from app.services.studio_model_images import export_selfie_flag_for_phone_exif

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
    refined_prompt_full: str | None = None,
    motion_video_prompt_auto: str | None = None,
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

    model_row: UserStudioModel | None = None
    if studio_model_id is not None:
        stmt = (
            select(UserStudioModel)
            .where(UserStudioModel.id == studio_model_id)
            .options(selectinload(UserStudioModel.images))
        )
        model_row = (await session.execute(stmt)).scalar_one_or_none()
    if model_row is not None and (model_row.camera_preset_id or "").strip():
        from app.services.studio_camera_presets import get_camera_preset_by_id
        from app.services.studio_phone_export import apply_phone_export_to_jpeg

        preset = get_camera_preset_by_id(model_row.camera_preset_id.strip())
        if preset:
            selfie_for_exif = export_selfie_flag_for_phone_exif(list(model_row.images))
            export_bytes = await anyio.to_thread.run_sync(
                partial(
                    apply_phone_export_to_jpeg,
                    data,
                    preset=preset,
                    selfie=selfie_for_exif,
                    export_lat=model_row.export_lat,
                    export_lon=model_row.export_lon,
                ),
            )
            if export_bytes is not None:
                data = export_bytes
                ext, media = ".jpg", "image/jpeg"

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
    full_store = (refined_prompt_full or refined_prompt or "").strip() or None
    row = StudioGeneration(
        user_id=owner_id,
        relative_path=rel.replace("\\", "/"),
        content_type=media,
        output_aspect=output_aspect,
        studio_model_id=studio_model_id,
        prompt_excerpt=excerpt,
        refined_prompt=full_store,
        motion_video_prompt_auto=(motion_video_prompt_auto or "").strip() or None,
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
