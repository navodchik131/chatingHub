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
from app.services.studio_jobs import job_params, job_result_dict

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


async def find_studio_generation_by_job_id(
    session: AsyncSession,
    job_id: int,
) -> StudioGeneration | None:
    from app.services.studio_outfit_anchor import generation_is_hidden_outfit_anchor

    stmt = (
        select(StudioGeneration)
        .where(StudioGeneration.studio_job_id == job_id)
        .order_by(StudioGeneration.id.desc())
    )
    for row in (await session.execute(stmt)).scalars().all():
        if not generation_is_hidden_outfit_anchor(row):
            return row
    return None


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
    video_backend: str | None = None,
) -> StudioGeneration:
    """Создаёт запись processing, привязанную к job (идемпотентно по studio_job_id)."""
    existing = await find_studio_generation_by_job_id(session, studio_job_id)
    if existing is not None:
        return existing

    excerpt = (prompt_excerpt or "").strip()[:2000] or None
    preview = (preview_source_url or "").strip()[:2000] or None

    vb = (video_backend or "wavespeed").strip().lower() or "wavespeed"

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
        video_backend=vb,
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


def carousel_placeholder_ids_from_params(params: dict) -> list[int]:
    """ID заглушек кадров карусели из params job."""
    raw = params.get("carousel_placeholder_ids")
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for item in raw:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


async def reserve_carousel_shot_placeholders(
    session: AsyncSession,
    *,
    owner_id: int,
    studio_job_id: int,
    count: int,
    studio_model_id: int | None,
    output_aspect: str | None,
    carousel_parent_generation_id: int | None = None,
    prompt_base: str = "Карусель",
) -> list[StudioGeneration]:
    """
    Создаёт N записей processing до старта WaveSpeed — видны в архиве после F5 / с другого устройства.
    studio_job_id нужен для reconcile; сами кадры ищем по carousel_placeholder_ids в params job.
    """
    n = max(2, min(8, int(count)))
    rows: list[StudioGeneration] = []
    for shot_i in range(n):
        excerpt = f"{prompt_base} {shot_i + 1}/{n}…".strip()[:2000]
        row = StudioGeneration(
            user_id=owner_id,
            status=StudioGenerationStatus.PROCESSING,
            relative_path="",
            content_type="image/jpeg",
            output_aspect=output_aspect,
            studio_model_id=studio_model_id,
            studio_job_id=int(studio_job_id),
            prompt_excerpt=excerpt,
            carousel_parent_generation_id=carousel_parent_generation_id,
            carousel_shot_index=shot_i,
            video_backend="wavespeed",
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    from app.services.funnel_analytics import record_funnel_event_for_owner_once

    await record_funnel_event_for_owner_once(
        session, owner_id=owner_id, event="first_generation"
    )
    log.info(
        "carousel placeholders job=%s shots=%s ids=%s",
        studio_job_id,
        n,
        [r.id for r in rows],
    )
    return rows


async def mark_carousel_placeholders_failed_from(
    session: AsyncSession,
    placeholder_ids: list[int],
    *,
    start_index: int,
    message: str,
) -> int:
    """Помечает незавершённые кадры карусели (с start_index) как failed."""
    changed = 0
    msg = (message or "").strip() or "Кадр карусели не сгенерирован"
    for i in range(max(0, int(start_index)), len(placeholder_ids)):
        row = await session.get(StudioGeneration, int(placeholder_ids[i]))
        if row is None:
            continue
        st = (row.status or "").strip()
        if st in (StudioGenerationStatus.READY, StudioGenerationStatus.FAILED):
            continue
        await mark_studio_generation_failed(session, row, message=msg, step="carousel")
        changed += 1
    return changed


async def finalize_carousel_placeholders_for_terminal_job(
    session: AsyncSession,
    job: StudioJob,
) -> bool:
    """Закрывает зависшие заглушки карусели, когда job completed/failed."""
    if (job.job_type or "").strip() != "carousel":
        return False
    if job.status not in (
        StudioJobStatus.failed.value,
        StudioJobStatus.completed.value,
    ):
        return False
    params = job_params(job)
    ph_ids = carousel_placeholder_ids_from_params(params)
    if not ph_ids:
        return False

    completed_ids: set[int] = set()
    if job.status == StudioJobStatus.completed.value:
        result = job_result_dict(job)
        for item in result.get("items") or []:
            if isinstance(item, dict):
                try:
                    completed_ids.add(int(item.get("generation_id")))
                except (TypeError, ValueError):
                    pass

    changed = 0
    fail_msg = (job.error_message or "").strip() or "Генерация не выполнена"
    for gid in ph_ids:
        row = await session.get(StudioGeneration, gid)
        if row is None:
            continue
        st = (row.status or "").strip()
        if st in (StudioGenerationStatus.READY, StudioGenerationStatus.FAILED):
            continue
        if gid in completed_ids and generation_has_archive_file(row):
            continue
        if job.status == StudioJobStatus.failed.value:
            await mark_studio_generation_failed(
                session, row, message=fail_msg, step="job"
            )
            changed += 1
        elif st == StudioGenerationStatus.PROCESSING:
            await mark_studio_generation_failed(
                session,
                row,
                message="Задача завершена без файла результата",
                step="job",
            )
            changed += 1
    if changed:
        log.info("carousel finalize placeholders job=%s changed=%s", job.id, changed)
    return changed > 0


def generation_media_kind(row: StudioGeneration) -> str:
    ct = (row.content_type or "").strip().lower()
    return "video" if ct.startswith("video/") else "image"


async def resolve_studio_generation_for_job(
    session: AsyncSession,
    job: StudioJob,
) -> StudioGeneration | None:
    # placeholder_generation_id — основной результат job; job_id может дублироваться у скрытого outfit ref.
    ph = job_params(job).get("placeholder_generation_id")
    if isinstance(ph, int):
        row = await session.get(StudioGeneration, ph)
        if row is not None:
            return row
    if isinstance(ph, str) and ph.isdigit():
        row = await session.get(StudioGeneration, int(ph))
        if row is not None:
            return row
    return await find_studio_generation_by_job_id(session, job.id)


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
    if (job.job_type or "").strip() == "carousel":
        return await finalize_carousel_placeholders_for_terminal_job(session, job)
    gen = await resolve_studio_generation_for_job(session, job)
    if gen is None:
        return False
    st = (gen.status or "").strip()
    if st in (StudioGenerationStatus.READY, StudioGenerationStatus.FAILED):
        return False

    if job.status == StudioJobStatus.failed.value:
        ws_key = ""
        try:
            sub_b, _, ws_row, plan, _credits, _demo = await load_owner_studio_billing(
                session, gen.user_id
            )
            ws_key = studio_wavespeed_api_key(
                plan=plan,
                ws_row=ws_row,
                owner_subscription=sub_b,
                demo_generations_remaining=_demo,
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
