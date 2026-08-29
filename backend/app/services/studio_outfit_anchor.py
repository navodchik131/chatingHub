"""Сохранение dressed-body / outfit anchor в архив и привязка к master-генерации."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.db.models import StudioGeneration
from app.services.studio_generation_storage import persist_studio_generation_from_uploaded_bytes

log = logging.getLogger(__name__)

OUTFIT_ANCHOR_PROMPT_TAG = "[Outfit anchor]"
MOTION_DRESS_PROMPT_TAG = "Motion Control dress"


async def persist_outfit_anchor_generation(
    session: AsyncSession,
    *,
    owner_id: int,
    studio_model_id: int | None,
    dressed_bytes: bytes,
    output_aspect: str | None,
    source_job_id: int | None = None,
    prompt_note: str = "",
) -> StudioGeneration | None:
    """Сохраняет dressed body как отдельную генерацию-референс для карусели и последующих img2img."""
    if not dressed_bytes or len(dressed_bytes) < 64:
        return None
    note = (prompt_note or "").strip()
    refined = OUTFIT_ANCHOR_PROMPT_TAG
    if note:
        refined = f"{OUTFIT_ANCHOR_PROMPT_TAG} {note}".strip()
    # Не привязываем к studio_job_id: иначе find_studio_generation_by_job_id
    # вернёт outfit вместо итоговой генерации и сломает recovery/архив.
    _ = source_job_id
    row = await persist_studio_generation_from_uploaded_bytes(
        session,
        owner_id=owner_id,
        data=dressed_bytes,
        content_type="image/jpeg",
        output_aspect=output_aspect,
        studio_model_id=studio_model_id,
        refined_prompt=refined,
        motion_video_prompt_auto=None,
        studio_job_id=None,
    )
    if row is not None:
        log.info(
            "outfit anchor saved gen_id=%s model_id=%s job_id=%s",
            row.id,
            studio_model_id,
            source_job_id,
        )
    return row


async def link_outfit_to_generation(
    session: AsyncSession,
    *,
    generation: StudioGeneration,
    outfit_generation_id: int | None,
) -> None:
    """Привязывает outfit anchor к master-результату (если колонка есть)."""
    if outfit_generation_id is None or generation is None:
        return
    if getattr(generation, "outfit_generation_id", None) == outfit_generation_id:
        return
    generation.outfit_generation_id = int(outfit_generation_id)
    session.add(generation)
    await session.flush()


async def find_outfit_generation_for_master(
    session: AsyncSession,
    master: StudioGeneration,
) -> int | None:
    """Outfit gen: явная ссылка на master или последний dress anchor той же модели."""
    linked = getattr(master, "outfit_generation_id", None)
    if linked:
        row = await session.get(StudioGeneration, int(linked))
        if row and row.user_id == master.user_id:
            return int(linked)

    mid = master.studio_model_id
    if mid is None:
        return None

    stmt = (
        select(StudioGeneration)
        .where(
            StudioGeneration.user_id == master.user_id,
            StudioGeneration.studio_model_id == mid,
            StudioGeneration.id != master.id,
        )
        .order_by(StudioGeneration.created_at.desc())
        .limit(30)
    )
    rows = (await session.execute(stmt)).scalars().all()
    master_ts = master.created_at
    for row in rows:
        if master_ts and row.created_at and row.created_at > master_ts:
            continue
        blob = f"{row.prompt_excerpt or ''}\n{row.refined_prompt or ''}".lower()
        if (
            "outfit anchor" in blob
            or "motion control dress" in blob
            or MOTION_DRESS_PROMPT_TAG.lower() in blob
        ):
            return row.id
    return None


def generation_is_outfit_anchor(row: StudioGeneration | None) -> bool:
    """Outfit ref для карусели: явный anchor или шаг Motion Control dress."""
    if row is None:
        return False
    blob = f"{row.prompt_excerpt or ''}\n{row.refined_prompt or ''}".lower()
    return "outfit anchor" in blob or "motion control dress" in blob


def generation_is_hidden_outfit_anchor(row: StudioGeneration | None) -> bool:
    """Скрытый ref anchor ([Outfit anchor]) — не показываем в архиве пользователя."""
    if row is None:
        return False
    blob = f"{row.prompt_excerpt or ''}\n{row.refined_prompt or ''}".lower()
    return OUTFIT_ANCHOR_PROMPT_TAG.lower() in blob


def exclude_hidden_outfit_anchors_from_archive(stmt: Select) -> Select:
    """SQL-фильтр: убираем скрытые outfit anchor из списка архива."""
    hidden = or_(
        StudioGeneration.prompt_excerpt.ilike(f"%{OUTFIT_ANCHOR_PROMPT_TAG}%"),
        StudioGeneration.refined_prompt.ilike(f"%{OUTFIT_ANCHOR_PROMPT_TAG}%"),
    )
    return stmt.where(not_(hidden))
