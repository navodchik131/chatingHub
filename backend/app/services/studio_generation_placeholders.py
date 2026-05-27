"""Заглушки архива при старте studio_jobs — сразу видны в UI как «в процессе»."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StudioGeneration
from app.services.studio_generation_status import StudioGenerationStatus

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
    )
    session.add(row)
    await session.flush()
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
