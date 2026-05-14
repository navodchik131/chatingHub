from __future__ import annotations

import asyncio
import logging
import uuid
from functools import partial

import anyio
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import BACKEND_DIR, settings
from app.db.models import StudioGeneration, UserStudioModel
from app.services.studio_model_images import export_selfie_flag_for_phone_exif

log = logging.getLogger(__name__)

MAX_ARCHIVE_BYTES = 25 * 1024 * 1024

USER_HINT_ARCHIVE_DOWNLOAD_FAILED = (
    "Не удалось скачать файл результата на наш сервер (часто таймаут или нестабильная сеть до CDN). "
    "Временная ссылка провайдера ниже действует ограниченное время — нажмите «Сохранить в архив» в интерфейсе, "
    "чтобы повторить загрузку без повторной генерации."
)


def user_message_when_archive_download_failed(previous: str | None) -> str:
    prev = (previous or "").strip()
    if prev:
        return f"{prev}\n\n{USER_HINT_ARCHIVE_DOWNLOAD_FAILED}"
    return USER_HINT_ARCHIVE_DOWNLOAD_FAILED


async def persist_studio_generation_from_uploaded_bytes(
    session: AsyncSession,
    *,
    owner_id: int,
    data: bytes,
    content_type: str,
    output_aspect: str | None,
    studio_model_id: int | None,
    refined_prompt: str | None,
    motion_video_prompt_auto: str | None,
) -> StudioGeneration | None:
    """Сохраняет уже готовый кадр (upload) в архив студии без WaveSpeed."""
    if not data:
        return None
    if len(data) > MAX_ARCHIVE_BYTES:
        log.warning("studio archive (upload): file too large (%s bytes)", len(data))
        return None

    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in ("image/jpeg", "image/jpg"):
        ext, media = ".jpg", "image/jpeg"
    elif ct == "image/png":
        ext, media = ".png", "image/png"
    elif ct == "image/webp":
        ext, media = ".webp", "image/webp"
    elif ct == "image/gif":
        ext, media = ".gif", "image/gif"
    else:
        ext, media = ".jpg", "image/jpeg"

    model_row: UserStudioModel | None = None
    if studio_model_id is not None:
        stmt = (
            select(UserStudioModel)
            .where(UserStudioModel.id == studio_model_id)
            .options(selectinload(UserStudioModel.images))
        )
        model_row = (await session.execute(stmt)).scalar_one_or_none()
    out_data = data
    if model_row is not None and (model_row.camera_preset_id or "").strip():
        from app.services.studio_camera_presets import get_camera_preset_by_id
        from app.services.studio_phone_export import apply_phone_export_to_jpeg

        preset = get_camera_preset_by_id(model_row.camera_preset_id.strip())
        if preset:
            selfie_for_exif = export_selfie_flag_for_phone_exif(list(model_row.images))
            export_bytes = await anyio.to_thread.run_sync(
                partial(
                    apply_phone_export_to_jpeg,
                    out_data,
                    preset=preset,
                    selfie=selfie_for_exif,
                    export_lat=model_row.export_lat,
                    export_lon=model_row.export_lon,
                ),
            )
            if export_bytes is not None:
                out_data = export_bytes
                ext, media = ".jpg", "image/jpeg"

    rel = f"data/studio_generations/{owner_id}/{uuid.uuid4().hex}{ext}"
    path = (BACKEND_DIR / rel).resolve()
    try:
        path.relative_to(BACKEND_DIR.resolve())
    except ValueError:
        log.warning("studio archive (upload): bad path")
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out_data)

    rp = (refined_prompt or "").strip()
    excerpt = (rp[:2000] if rp else None) or None
    row = StudioGeneration(
        user_id=owner_id,
        relative_path=rel.replace("\\", "/"),
        content_type=media,
        output_aspect=output_aspect,
        studio_model_id=studio_model_id,
        prompt_excerpt=excerpt,
        refined_prompt=rp or None,
        motion_video_prompt_auto=(motion_video_prompt_auto or "").strip() or None,
        source_url=None,
    )
    session.add(row)
    await session.flush()
    return row


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

    attempts = max(1, int(settings.studio_archive_download_attempts))
    timeout = float(settings.studio_archive_download_timeout_seconds)
    data = b""
    r: httpx.Response | None = None
    last_err: Exception | None = None
    wait_s = 0.0

    for attempt in range(attempts):
        if wait_s > 0:
            await asyncio.sleep(wait_s)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                r = await client.get(url)
                r.raise_for_status()
                data = r.content
                break
        except Exception as e:
            last_err = e
            log.warning(
                "studio archive download attempt %s/%s failed (%s): %s",
                attempt + 1,
                attempts,
                url[:240],
                e,
            )
            wait_s = min(60.0, 3.0 * (2**attempt))

    else:
        log.warning(
            "studio archive download exhausted after %s attempts: %s", attempts, last_err
        )
        return None

    assert r is not None
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
