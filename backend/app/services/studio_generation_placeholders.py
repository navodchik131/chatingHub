"""Заглушки архива при старте studio_jobs — сразу видны в UI как «в процессе»."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StudioGeneration, StudioJob, StudioJobStatus
from app.services.studio_generation_status import StudioGenerationStatus
from app.services.studio_generation_storage import (
    generation_has_archive_file,
    mark_studio_generation_failed,
    try_recover_studio_generation_from_wavespeed,
)
from app.services.studio_model_images import normalize_exif_camera
from app.services.studio_keys import load_owner_studio_billing, studio_wavespeed_api_key
from app.services.studio_jobs import job_params

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


async def find_studio_generation_by_job_id(
    session: AsyncSession,
    job_id: int,
) -> StudioGeneration | None:
    stmt = (
        select(StudioGeneration)
        .where(StudioGeneration.studio_job_id == job_id)
        .order_by(StudioGeneration.id.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def reserve_studio_generation_for_job(
    session: AsyncSession,
    *,
    owner_id: int,
    studio_job_id: int,
    studio_model_id: int | None,
    output_aspect: str | None,
    content_type: str = "image/png",
    prompt_excerpt: str | None = None,
    preview_source_url: str | None = None,
    exif_camera: str | None = None,
) -> StudioGeneration:
    """Создаёт запись processing, привязанную к job (идемпотентно по studio_job_id)."""
    existing = await find_studio_generation_by_job_id(session, studio_job_id)
    if existing is not None:
        return existing

    excerpt = (prompt_excerpt or "").strip()[:2000] or None
    preview = (preview_source_url or "").strip()[:2000] or None

    row = StudioGeneration(
        user_id=owner_id,
        status=StudioGenerationStatus.PROCESSING,
        relative_path="",
        content_type=(content_type or "image/png").strip()[:64],
        output_aspect=output_aspect,
        studio_model_id=studio_model_id,
        studio_job_id=studio_job_id,
        prompt_excerpt=excerpt,
        source_url=preview,
        exif_camera=normalize_exif_camera(exif_camera),
    )
    session.add(row)
    await session.flush()
    from app.services.funnel_analytics import record_funnel_event_for_owner_once

    await record_funnel_event_for_owner_once(
        session, owner_id=owner_id, event="first_generation"
    )
    log.info(
        "studio placeholder gen=%s job=%s kind=%s",
        row.id,
        studio_job_id,
        row.content_type,
    )
    return row


def generation_media_kind(row: StudioGeneration) -> str:
    ct = (row.content_type or "").strip().lower()
    return "video" if ct.startswith("video/") else "image"


async def resolve_studio_generation_for_job(
    session: AsyncSession,
    job: StudioJob,
) -> StudioGeneration | None:
    row = await find_studio_generation_by_job_id(session, job.id)
    if row is not None:
        return row
    ph = job_params(job).get("placeholder_generation_id")
    if isinstance(ph, int):
        return await session.get(StudioGeneration, ph)
    if isinstance(ph, str) and ph.isdigit():
        return await session.get(StudioGeneration, int(ph))
    return None


async def finalize_studio_generation_for_terminal_job(
    session: AsyncSession,
    job: StudioJob,
) -> bool:
    """Синхронизирует placeholder с завершённой задачей (failed/completed без файла)."""
    if job.status not in (
        StudioJobStatus.failed.value,
        StudioJobStatus.completed.value,
    ):
        return False
    gen = await resolve_studio_generation_for_job(session, job)
    if gen is None:
        return False
    st = (gen.status or "").strip()
    if st in (StudioGenerationStatus.READY, StudioGenerationStatus.FAILED):
        return False

    if job.status == StudioJobStatus.failed.value:
        ws_key = ""
        try:
            sub_b, _, ws_row, plan, _credits = await load_owner_studio_billing(
                session, gen.user_id
            )
            ws_key = studio_wavespeed_api_key(
                plan=plan, ws_row=ws_row, owner_subscription=sub_b
            )
        except Exception:
            log.exception("studio recover: billing load failed gen=%s", gen.id)
        if (ws_key or "").strip() and await try_recover_studio_generation_from_wavespeed(
            session, gen, api_key=ws_key
        ):
            return True
        await mark_studio_generation_failed(
            session,
            gen,
            message=(job.error_message or "").strip() or "Генерация не выполнена",
            step="job",
        )
        return True

    if job.status == StudioJobStatus.completed.value and st == StudioGenerationStatus.PROCESSING:
        has_file = generation_has_archive_file(gen)
        has_src = bool((gen.source_url or "").strip())
        if not has_file and not has_src:
            await mark_studio_generation_failed(
                session,
                gen,
                message="Задача завершена без файла результата",
                step="job",
            )
            return True
    return False


async def reconcile_stuck_studio_generations(
    session: AsyncSession,
    owner_id: int,
    *,
    limit: int = 30,
) -> int:
    """Помечает зависшие processing/archiving, если связанная studio_job уже завершилась."""
    stmt = (
        select(StudioGeneration)
        .where(StudioGeneration.user_id == owner_id)
        .where(
            StudioGeneration.status.in_(
                (
                    StudioGenerationStatus.PROCESSING,
                    StudioGenerationStatus.ARCHIVING,
                )
            )
        )
        .order_by(StudioGeneration.created_at.desc(), StudioGeneration.id.desc())
        .limit(max(1, int(limit)))
    )
    changed = 0
    for gen in (await session.execute(stmt)).scalars().all():
        jid = gen.studio_job_id
        if not jid:
            continue
        job = await session.get(StudioJob, jid)
        if job is None:
            await mark_studio_generation_failed(
                session,
                gen,
                message="Связанная задача не найдена",
                step="orphan",
            )
            changed += 1
            continue
        if await finalize_studio_generation_for_terminal_job(session, job):
            changed += 1
    if changed:
        log.info("studio reconcile stuck generations owner=%s count=%s", owner_id, changed)
    return changed


def generation_is_pending_in_ui(row: StudioGeneration) -> bool:
    from app.services.studio_generation_storage import generation_has_archive_file

    st = (row.status or "").strip()
    if st in (
        StudioGenerationStatus.PROCESSING,
        StudioGenerationStatus.ARCHIVING,
    ):
        return True
    if st == StudioGenerationStatus.PROVIDER_READY:
        if generation_media_kind(row) == "video":
            return not (row.source_url or "").strip().startswith("https://")
        return not generation_has_archive_file(row)
    return False
