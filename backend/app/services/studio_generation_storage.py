from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import TYPE_CHECKING, Any

import anyio
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import BACKEND_DIR, settings
from app.db.models import StudioGeneration, UserStudioModel
from app.db.session import SessionLocal
from app.services.studio_generation_status import StudioGenerationStatus
from app.services.studio_model_images import exif_camera_is_selfie, normalize_exif_camera

if TYPE_CHECKING:
    pass

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


def generation_has_archive_file(row: StudioGeneration) -> bool:
    rel = (row.relative_path or "").strip()
    if not rel:
        return False
    path = (BACKEND_DIR / rel).resolve()
    try:
        path.relative_to(BACKEND_DIR.resolve())
    except ValueError:
        return False
    return path.is_file()


async def begin_studio_generation_run(
    session: AsyncSession,
    *,
    owner_id: int,
    output_aspect: str | None,
    studio_model_id: int | None,
    studio_job_id: int | None = None,
    exif_camera: str | None = None,
) -> StudioGeneration:
    if studio_job_id is not None:
        from app.services.studio_generation_placeholders import (
            find_studio_generation_by_job_id,
        )

        existing = await find_studio_generation_by_job_id(session, studio_job_id)
        if existing is not None:
            return existing
    row = StudioGeneration(
        user_id=owner_id,
        status=StudioGenerationStatus.PROCESSING,
        relative_path="",
        content_type="image/png",
        output_aspect=output_aspect,
        studio_model_id=studio_model_id,
        studio_job_id=studio_job_id,
        exif_camera=normalize_exif_camera(exif_camera),
    )
    session.add(row)
    await session.flush()
    from app.services.funnel_analytics import record_funnel_event_for_owner_once

    await record_funnel_event_for_owner_once(
        session, owner_id=owner_id, event="first_generation"
    )
    return row


async def mark_studio_generation_failed(
    session: AsyncSession,
    row: StudioGeneration,
    *,
    message: str | None,
    step: str,
) -> None:
    row.status = StudioGenerationStatus.FAILED
    row.error_message = ((message or "").strip()[:4000] or None)
    row.error_step = (step or "").strip()[:32] or None
    session.add(row)
    await session.flush()


async def attach_studio_generation_wavespeed_task(
    session: AsyncSession,
    row: StudioGeneration,
    *,
    task_id: str,
) -> None:
    """Сохраняет task_id WaveSpeed, пока запись ещё в processing (для восстановления после 504)."""
    tid = (task_id or "").strip()
    if not tid:
        return
    row.wavespeed_task_id = tid[:128]
    session.add(row)
    await session.flush()


async def mark_studio_generation_provider_ready(
    session: AsyncSession,
    row: StudioGeneration,
    *,
    source_url: str,
    wavespeed_task_id: str | None = None,
) -> None:
    url = (source_url or "").strip()
    row.source_url = url[:2000] if url else None
    tid = (wavespeed_task_id or "").strip()
    row.wavespeed_task_id = tid[:128] if tid else None
    row.status = StudioGenerationStatus.PROVIDER_READY
    row.error_message = None
    row.error_step = None
    session.add(row)
    await session.flush()


async def _download_bytes_from_url(url: str) -> tuple[bytes | None, str | None]:
    """Скачивает по HTTPS; возвращает (bytes, content_type_header)."""
    u = (url or "").strip()
    if not u:
        return None, None
    attempts = max(1, int(settings.studio_archive_download_attempts))
    timeout = float(settings.studio_archive_download_timeout_seconds)
    wait_s = 0.0
    last_err: Exception | None = None
    r: httpx.Response | None = None
    for attempt in range(attempts):
        if wait_s > 0:
            await asyncio.sleep(wait_s)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                r = await client.get(u)
                r.raise_for_status()
                data = r.content
                ct = (r.headers.get("content-type") or "").split(";")[0].strip().lower()
                return data, ct or None
        except Exception as e:
            last_err = e
            log.warning(
                "studio archive download attempt %s/%s failed (%s): %s",
                attempt + 1,
                attempts,
                u[:240],
                e,
            )
            wait_s = min(60.0, 3.0 * (2**attempt))
    log.warning("studio archive download exhausted: %s", last_err)
    return None, None


def _ext_and_media_from_content_type(ct_header: str | None) -> tuple[str, str]:
    ct = (ct_header or "").split(";")[0].strip().lower()
    if "png" in ct:
        return ".png", "image/png"
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg", "image/jpeg"
    if "webp" in ct:
        return ".webp", "image/webp"
    if "gif" in ct:
        return ".gif", "image/gif"
    if "quicktime" in ct or "mp4" in ct:
        return ".mp4", "video/mp4"
    if "webm" in ct:
        return ".webm", "video/webm"
    return ".png", "image/png"


async def _apply_ai_metadata_strip_if_needed(
    data: bytes,
    ext: str,
    media: str,
) -> tuple[bytes, str, str]:
    if not (media or "").startswith("image/"):
        return data, ext, media
    from app.services.studio_ai_metadata_strip import strip_ai_metadata_from_image_bytes

    stripped, did_strip = await anyio.to_thread.run_sync(
        partial(strip_ai_metadata_from_image_bytes, data, ext=ext)
    )
    if did_strip:
        return stripped, ext, media
    return data, ext, media


async def _apply_analog_humanize_if_needed(
    data: bytes,
    ext: str,
    media: str,
) -> tuple[bytes, str, str, bool]:
    if not (media or "").startswith("image/"):
        return data, ext, media, False
    from app.services.studio_ai_metadata_strip import apply_analog_humanize_to_image_bytes

    out_bytes, applied = await anyio.to_thread.run_sync(
        partial(apply_analog_humanize_to_image_bytes, data, ext=ext)
    )
    if applied:
        return out_bytes, ext, media, True
    return data, ext, media, False


async def _apply_phone_export_if_needed(
    session: AsyncSession,
    *,
    studio_model_id: int | None,
    exif_camera: str | None,
    data: bytes,
    ext: str,
    media: str,
    skip_grain: bool = False,
) -> tuple[bytes, str, str]:
    if studio_model_id is None:
        return data, ext, media
    stmt = (
        select(UserStudioModel)
        .where(UserStudioModel.id == studio_model_id)
        .options(selectinload(UserStudioModel.images))
    )
    model_row = (await session.execute(stmt)).scalar_one_or_none()
    if model_row is None:
        return data, ext, media
    from app.services.studio_exif_profile import resolve_phone_export_preset
    from app.services.studio_phone_export import apply_phone_export_to_jpeg

    selfie_for_exif = exif_camera_is_selfie(exif_camera)
    preset = resolve_phone_export_preset(
        phone_exif_selfie_json=model_row.phone_exif_selfie_json,
        phone_exif_main_json=model_row.phone_exif_main_json,
        camera_preset_id=model_row.camera_preset_id,
        selfie=selfie_for_exif,
    )
    if not preset:
        return data, ext, media
    export_bytes = await anyio.to_thread.run_sync(
        partial(
            apply_phone_export_to_jpeg,
            data,
            preset=preset,
            selfie=selfie_for_exif,
            export_lat=model_row.export_lat,
            export_lon=model_row.export_lon,
            skip_grain=skip_grain,
        ),
    )
    if export_bytes is not None:
        return export_bytes, ".jpg", "image/jpeg"
    return data, ext, media


async def _apply_video_metadata_if_needed(
    session: AsyncSession,
    *,
    studio_model_id: int | None,
    exif_camera: str | None,
    data: bytes,
    ext: str,
    media: str,
) -> tuple[bytes, str, str]:
    if not (media or "").startswith("video/"):
        return data, ext, media
    from app.services.studio_exif_profile import resolve_phone_export_preset
    from app.services.studio_video_metadata import process_video_archive_bytes

    selfie_for_exif = exif_camera_is_selfie(exif_camera)
    preset: dict[str, Any] | None = None
    export_lat: float | None = None
    export_lon: float | None = None

    if studio_model_id is not None:
        stmt = (
            select(UserStudioModel)
            .where(UserStudioModel.id == studio_model_id)
            .options(selectinload(UserStudioModel.images))
        )
        model_row = (await session.execute(stmt)).scalar_one_or_none()
        if model_row is not None:
            export_lat = model_row.export_lat
            export_lon = model_row.export_lon
            preset = resolve_phone_export_preset(
                phone_exif_selfie_json=model_row.phone_exif_selfie_json,
                phone_exif_main_json=model_row.phone_exif_main_json,
                camera_preset_id=model_row.camera_preset_id,
                selfie=selfie_for_exif,
            )

    out_bytes, changed = await anyio.to_thread.run_sync(
        partial(
            process_video_archive_bytes,
            data,
            ext=ext,
            preset=preset,
            selfie=selfie_for_exif,
            export_lat=export_lat,
            export_lon=export_lon,
        ),
    )
    if changed and out_bytes:
        return out_bytes, ext, media
    return data, ext, media


async def _write_generation_file(
    session: AsyncSession,
    row: StudioGeneration,
    data: bytes,
    *,
    content_type_header: str | None,
    studio_model_id: int | None,
) -> bool:
    if not data or len(data) > MAX_ARCHIVE_BYTES:
        if data and len(data) > MAX_ARCHIVE_BYTES:
            log.warning("studio archive: file too large (%s bytes)", len(data))
        return False

    ext, media = _ext_and_media_from_content_type(content_type_header)
    data, ext, media = await _apply_ai_metadata_strip_if_needed(data, ext, media)
    data, ext, media, humanized = await _apply_analog_humanize_if_needed(data, ext, media)
    exif_cam = normalize_exif_camera(getattr(row, "exif_camera", None))
    data, ext, media = await _apply_phone_export_if_needed(
        session,
        studio_model_id=studio_model_id,
        exif_camera=exif_cam,
        data=data,
        ext=ext,
        media=media,
        skip_grain=humanized,
    )
    data, ext, media = await _apply_video_metadata_if_needed(
        session,
        studio_model_id=studio_model_id,
        exif_camera=exif_cam,
        data=data,
        ext=ext,
        media=media,
    )

    rel = f"data/studio_generations/{row.user_id}/{uuid.uuid4().hex}{ext}"
    path = (BACKEND_DIR / rel).resolve()
    try:
        path.relative_to(BACKEND_DIR.resolve())
    except ValueError:
        log.warning("studio archive: bad path")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    row.relative_path = rel.replace("\\", "/")
    row.content_type = media
    row.status = StudioGenerationStatus.READY
    row.error_message = None
    row.error_step = None
    session.add(row)
    await session.flush()
    return True


async def archive_studio_generation_from_bytes(
    session: AsyncSession,
    row: StudioGeneration,
    data: bytes,
    *,
    content_type: str | None = None,
    studio_model_id: int | None = None,
) -> bool:
    row.status = StudioGenerationStatus.ARCHIVING
    session.add(row)
    await session.flush()
    mid = studio_model_id if studio_model_id is not None else row.studio_model_id
    ok = await _write_generation_file(
        session,
        row,
        data,
        content_type_header=content_type,
        studio_model_id=mid,
    )
    if not ok and row.source_url:
        row.status = StudioGenerationStatus.PROVIDER_READY
        session.add(row)
        await session.flush()
    return ok


async def archive_studio_generation_from_url(
    session: AsyncSession,
    row: StudioGeneration,
    *,
    source_url: str | None = None,
    refined_prompt_full: str | None = None,
) -> bool:
    if generation_has_archive_file(row):
        row.status = StudioGenerationStatus.READY
        session.add(row)
        await session.flush()
        return True

    url = (source_url or row.source_url or "").strip()
    if not url:
        return False

    row.status = StudioGenerationStatus.ARCHIVING
    session.add(row)
    await session.flush()

    data, ct = await _download_bytes_from_url(url)
    if data is None:
        row.status = StudioGenerationStatus.PROVIDER_READY
        session.add(row)
        await session.flush()
        return False

    if refined_prompt_full:
        rp = refined_prompt_full.strip()
        row.refined_prompt = rp or row.refined_prompt
        row.prompt_excerpt = (rp[:2000] if rp else None) or row.prompt_excerpt

    return await _write_generation_file(
        session,
        row,
        data,
        content_type_header=ct,
        studio_model_id=row.studio_model_id,
    )


async def studio_finish_image_generation(
    session: AsyncSession,
    *,
    gen_row: StudioGeneration | None,
    owner_id: int,
    studio_model_id: int | None,
    output_aspect: str | None,
    refined_prompt: str,
    source_url: str | None = None,
    wavespeed_task_id: str | None = None,
    uploaded_bytes: bytes | None = None,
    uploaded_content_type: str = "image/png",
    motion_video_prompt_auto: str | None = None,
    exif_camera: str | None = None,
) -> tuple[StudioGeneration | None, str | None]:
    """
    Завершает пайплайн: provider_ready + попытка архива, либо сразу ready из байтов.
    Возвращает (запись, URL для превью — CDN или уже не нужен вызывающему).
    """
    rp = (refined_prompt or "").strip()
    excerpt = (rp[:2000] if rp else None) or None
    mva = (motion_video_prompt_auto or "").strip() or None

    row = gen_row
    if row is None and not uploaded_bytes and not (source_url or "").strip():
        return None, None

    if row is None:
        row = await begin_studio_generation_run(
            session,
            owner_id=owner_id,
            output_aspect=output_aspect,
            studio_model_id=studio_model_id,
            exif_camera=exif_camera,
        )
    elif exif_camera is not None:
        row.exif_camera = normalize_exif_camera(exif_camera)

    if rp:
        row.refined_prompt = rp
        row.prompt_excerpt = excerpt
    if mva:
        row.motion_video_prompt_auto = mva
    if output_aspect:
        row.output_aspect = output_aspect
    if studio_model_id is not None:
        row.studio_model_id = studio_model_id

    preview_url = (source_url or "").strip() or None

    if uploaded_bytes:
        ok = await archive_studio_generation_from_bytes(
            session,
            row,
            uploaded_bytes,
            content_type=uploaded_content_type,
            studio_model_id=studio_model_id,
        )
        if ok:
            preview_url = None
        return row, preview_url

    url = (source_url or "").strip()
    if url:
        await mark_studio_generation_provider_ready(
            session,
            row,
            source_url=url,
            wavespeed_task_id=wavespeed_task_id,
        )
        if await archive_studio_generation_from_url(
            session, row, source_url=url, refined_prompt_full=rp or None
        ):
            preview_url = None

    return row, preview_url


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
    studio_job_id: int | None = None,
    existing_row: StudioGeneration | None = None,
    exif_camera: str | None = None,
) -> StudioGeneration | None:
    """Сохраняет уже готовый кадр (upload) в архив студии без WaveSpeed."""
    if not data:
        return None
    rp = (refined_prompt or "").strip()
    excerpt = (rp[:2000] if rp else None) or None
    row = existing_row
    if row is None:
        row = await begin_studio_generation_run(
            session,
            owner_id=owner_id,
            output_aspect=output_aspect,
            studio_model_id=studio_model_id,
            studio_job_id=studio_job_id,
            exif_camera=exif_camera,
        )
    elif exif_camera is not None:
        row.exif_camera = normalize_exif_camera(exif_camera)
    row.refined_prompt = rp or None
    row.prompt_excerpt = excerpt
    row.motion_video_prompt_auto = (motion_video_prompt_auto or "").strip() or None
    if await archive_studio_generation_from_bytes(
        session,
        row,
        data,
        content_type=content_type,
        studio_model_id=studio_model_id,
    ):
        return row
    return None


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
    existing_row: StudioGeneration | None = None,
    exif_camera: str | None = None,
) -> StudioGeneration | None:
    """Скачивает картинку с WaveSpeed/CDN и сохраняет в data/studio_generations/…"""
    url = (source_url or "").strip()
    if not url:
        return None
    rp = (refined_prompt_full or refined_prompt or "").strip()
    resolved_exif = exif_camera
    if resolved_exif is None and existing_row is not None:
        resolved_exif = getattr(existing_row, "exif_camera", None)
    row, _ = await studio_finish_image_generation(
        session,
        gen_row=existing_row,
        owner_id=owner_id,
        studio_model_id=studio_model_id,
        output_aspect=output_aspect,
        refined_prompt=rp,
        source_url=url,
        motion_video_prompt_auto=motion_video_prompt_auto,
        exif_camera=resolved_exif,
    )
    if row is None:
        return None
    if row.status == StudioGenerationStatus.READY and generation_has_archive_file(row):
        return row
    if row.status == StudioGenerationStatus.PROVIDER_READY:
        return row
    return None


async def try_recover_studio_generation_from_wavespeed(
    session: AsyncSession,
    row: StudioGeneration,
    *,
    api_key: str,
    refined_prompt: str | None = None,
) -> bool:
    """
    Догружает результат, если задача WaveSpeed уже completed, а у нас failed/processing.
    """
    from app.services.studio_generation_status import StudioGenerationStatus
    from app.services.wavespeed_client import (
        WaveSpeedImageResult,
        format_wavespeed_user_error,
        wavespeed_poll_image_by_task_id,
    )

    tid = (row.wavespeed_task_id or "").strip()
    if not tid:
        return False
    st = (row.status or "").strip()
    if st == StudioGenerationStatus.READY and generation_has_archive_file(row):
        return False
    rp = (refined_prompt or row.refined_prompt or row.prompt_excerpt or "").strip()
    try:
        ws_res: WaveSpeedImageResult = await wavespeed_poll_image_by_task_id(
            api_key=api_key,
            task_id=tid,
            max_polls=45,
            poll_interval=2.0,
        )
    except Exception as e:
        log.info(
            "studio recover gen=%s task=%s: %s",
            row.id,
            tid,
            format_wavespeed_user_error(str(e))[:200],
        )
        return False

    _, _preview = await studio_finish_image_generation(
        session,
        gen_row=row,
        owner_id=row.user_id,
        studio_model_id=row.studio_model_id,
        output_aspect=row.output_aspect,
        refined_prompt=rp,
        source_url=ws_res.url,
        wavespeed_task_id=ws_res.task_id or tid,
    )
    await session.flush()
    if row.status == StudioGenerationStatus.READY and generation_has_archive_file(row):
        log.info("studio recover gen=%s task=%s: archived", row.id, tid)
        return True
    if (row.source_url or "").strip().startswith("https://"):
        log.info("studio recover gen=%s task=%s: provider_ready", row.id, tid)
        return True
    return False


async def resolve_wavespeed_image_job_after_error(
    session: AsyncSession,
    gen_row: StudioGeneration | None,
    *,
    api_key: str,
    refined_prompt: str | None,
    error_message: str,
) -> tuple[str | None, bool]:
    """
    После ошибки WaveSpeed image-edit: попытка догрузить результат или отложить (processing).
    Returns (recovered_image_url, deferred_pending).
    """
    from app.services.wavespeed_client import (
        wavespeed_is_gateway_timeout_error,
        wavespeed_is_image_poll_timeout_error,
    )

    if gen_row is None or not (gen_row.wavespeed_task_id or "").strip():
        return None, False
    if await try_recover_studio_generation_from_wavespeed(
        session,
        gen_row,
        api_key=api_key,
        refined_prompt=refined_prompt,
    ):
        url = (gen_row.source_url or "").strip()
        if url.startswith("https://"):
            return url, False
        if generation_has_archive_file(gen_row):
            return url or "ready", False
    if wavespeed_is_image_poll_timeout_error(error_message) or wavespeed_is_gateway_timeout_error(
        error_message
    ):
        gen_row.status = StudioGenerationStatus.PROCESSING
        gen_row.error_message = None
        gen_row.error_step = None
        session.add(gen_row)
        await session.flush()
        log.info(
            "studio wavespeed image deferred gen=%s task=%s",
            gen_row.id,
            gen_row.wavespeed_task_id,
        )
        return None, True
    return None, False


async def recover_recent_failed_studio_generations(
    session: AsyncSession,
    owner_id: int,
    *,
    limit: int = 5,
) -> int:
    """При опросе pending: подтянуть failed-записи, у которых WaveSpeed уже отдал результат."""
    from app.services.studio_generation_status import StudioGenerationStatus
    from app.services.studio_keys import load_owner_studio_billing, studio_wavespeed_api_key

    recover_cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    stmt = (
        select(StudioGeneration)
        .where(StudioGeneration.user_id == owner_id)
        .where(StudioGeneration.wavespeed_task_id.isnot(None))
        .where(StudioGeneration.status == StudioGenerationStatus.FAILED)
        .where(StudioGeneration.created_at >= recover_cutoff)
        .order_by(StudioGeneration.created_at.desc())
        .limit(max(1, int(limit)))
    )
    rows = list((await session.execute(stmt)).scalars().all())
    if not rows:
        return 0
    sub_b, _, ws_row, plan, _credits, _demo = await load_owner_studio_billing(session, owner_id)
    ws_key = studio_wavespeed_api_key(
        plan=plan,
        ws_row=ws_row,
        owner_subscription=sub_b,
        demo_generations_remaining=_demo,
    )
    if not (ws_key or "").strip():
        return 0
    done = 0
    for row in rows:
        if await try_recover_studio_generation_from_wavespeed(
            session, row, api_key=ws_key
        ):
            done += 1
    return done


async def retry_pending_studio_archives() -> int:
    """Догружает архив для provider_ready; помечает устаревшие processing как failed."""
    from app.db.models import StudioJob, StudioJobStatus
    from app.services.studio_generation_placeholders import (
        finalize_studio_generation_for_terminal_job,
    )

    batch = max(1, int(settings.studio_archive_retry_batch_size))
    stale_h = max(1, int(settings.studio_generation_stale_processing_hours))
    stale_cutoff = datetime.now(timezone.utc) - timedelta(hours=stale_h)
    done = 0

    async with SessionLocal() as session:
        terminal_stmt = (
            select(StudioGeneration)
            .where(StudioGeneration.status == StudioGenerationStatus.PROCESSING)
            .where(StudioGeneration.studio_job_id.isnot(None))
            .order_by(StudioGeneration.created_at.asc())
            .limit(batch)
        )
        for gen in (await session.execute(terminal_stmt)).scalars().all():
            job = await session.get(StudioJob, int(gen.studio_job_id))
            if job is None or job.status not in (
                StudioJobStatus.failed.value,
                StudioJobStatus.completed.value,
            ):
                continue
            if await finalize_studio_generation_for_terminal_job(session, job):
                done += 1
        if done:
            await session.commit()

    async with SessionLocal() as session:
        stale_stmt = (
            select(StudioGeneration)
            .where(StudioGeneration.status == StudioGenerationStatus.PROCESSING)
            .where(StudioGeneration.created_at < stale_cutoff)
            .limit(batch)
        )
        for row in (await session.execute(stale_stmt)).scalars().all():
            await mark_studio_generation_failed(
                session,
                row,
                message="Превышено время ожидания пайплайна генерации",
                step="timeout",
            )
            done += 1
        if done:
            await session.commit()

    async with SessionLocal() as session:
        stmt = (
            select(StudioGeneration)
            .where(StudioGeneration.status == StudioGenerationStatus.PROVIDER_READY)
            .where(StudioGeneration.source_url.isnot(None))
            .order_by(StudioGeneration.created_at.asc())
            .limit(batch)
        )
        rows = list((await session.execute(stmt)).scalars().all())
        for row in rows:
            if generation_has_archive_file(row):
                row.status = StudioGenerationStatus.READY
                session.add(row)
                done += 1
                continue
            if await archive_studio_generation_from_url(session, row):
                done += 1
        await session.commit()

    processing_cutoff = datetime.now(timezone.utc) - timedelta(minutes=3)
    async with SessionLocal() as session:
        from app.services.studio_keys import load_owner_studio_billing, studio_wavespeed_api_key

        processing_stmt = (
            select(StudioGeneration)
            .where(StudioGeneration.wavespeed_task_id.isnot(None))
            .where(StudioGeneration.status == StudioGenerationStatus.PROCESSING)
            .where(StudioGeneration.created_at < processing_cutoff)
            .order_by(StudioGeneration.created_at.asc())
            .limit(batch)
        )
        for row in (await session.execute(processing_stmt)).scalars().all():
            sub_b, _, ws_row, plan, _credits, _demo = await load_owner_studio_billing(
                session, row.user_id
            )
            ws_key = studio_wavespeed_api_key(
                plan=plan,
                ws_row=ws_row,
                owner_subscription=sub_b,
                demo_generations_remaining=_demo,
            )
            if not (ws_key or "").strip():
                continue
            if await try_recover_studio_generation_from_wavespeed(
                session, row, api_key=ws_key
            ):
                done += 1
        await session.commit()

    recover_cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    async with SessionLocal() as session:
        from app.services.studio_keys import load_owner_studio_billing, studio_wavespeed_api_key

        recover_stmt = (
            select(StudioGeneration)
            .where(StudioGeneration.wavespeed_task_id.isnot(None))
            .where(StudioGeneration.status == StudioGenerationStatus.FAILED)
            .where(StudioGeneration.created_at >= recover_cutoff)
            .order_by(StudioGeneration.created_at.desc())
            .limit(batch)
        )
        for row in (await session.execute(recover_stmt)).scalars().all():
            sub_b, _, ws_row, plan, _credits, _demo = await load_owner_studio_billing(
                session, row.user_id
            )
            ws_key = studio_wavespeed_api_key(
                plan=plan,
                ws_row=ws_row,
                owner_subscription=sub_b,
                demo_generations_remaining=_demo,
            )
            if not (ws_key or "").strip():
                continue
            if await try_recover_studio_generation_from_wavespeed(
                session, row, api_key=ws_key
            ):
                done += 1
        await session.commit()

    if done:
        log.info("studio archive retry: processed %s row(s)", done)
    return done


async def studio_finish_video_generation(
    session: AsyncSession,
    gen_row: StudioGeneration | None,
    *,
    video_url: str | None,
    prompt_excerpt: str | None = None,
) -> StudioGeneration | None:
    """Готовое видео: CDN URL в source_url, без обязательного локального mp4."""
    if gen_row is None:
        return None
    url = (video_url or "").strip()
    if not url:
        return None
    gen_row.content_type = "video/mp4"
    gen_row.source_url = url[:2000]
    gen_row.status = StudioGenerationStatus.PROVIDER_READY
    gen_row.error_message = None
    gen_row.error_step = None
    if prompt_excerpt:
        ex = prompt_excerpt.strip()[:2000]
        gen_row.prompt_excerpt = ex or gen_row.prompt_excerpt
    session.add(gen_row)
    await session.flush()
    return gen_row


def safe_delete_generation_file(relative_path: str) -> None:
    p = (BACKEND_DIR / relative_path).resolve()
    try:
        p.relative_to(BACKEND_DIR.resolve())
    except ValueError:
        return
    if p.is_file():
        p.unlink(missing_ok=True)
