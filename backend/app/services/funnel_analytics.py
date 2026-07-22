"""Воронка активации: запись событий и агрегаты для админки."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    FunnelEvent,
    StudioGeneration,
    UsageEvent,
    User,
    UserStudioModel,
    WavespeedConnection,
)
from app.services.workspace import workspace_owner_id

_FIRST_GENERATION_FUNNEL_EVENTS = frozenset(
    {
        "first_generation",
        "onboarding_generation_success",
    }
)

_STUDIO_GENERATION_USAGE_KINDS = frozenset(
    {
        "studio_prompt_refine",
        "studio_motion_first_frame",
        "studio_motion_control",
        "studio_image_upscale",
        "studio_video_upscale",
        "studio_carousel_shot",
        "studio_model_bootstrap_face_merge",
        "studio_model_bootstrap_body_compose",
        "studio_model_bootstrap_sheet",
    }
)

ALLOWED_FUNNEL_EVENTS = frozenset(
    {
        "signup",
        "workspace_opened",
        "integrations_opened",
        "ws_key_saved",
        "onboarding_wizard_opened",
        "onboarding_wizard_skipped",
        "onboarding_wizard_completed",
        "onboarding_model_photo_set",
        "onboarding_ref_photo_set",
        "onboarding_profile_generated",
        "onboarding_generate_clicked",
        "onboarding_generation_success",
        "onboarding_model_save_clicked",
        "onboarding_model_saved",
        "onboarding_ws_key_saved",
        "model_created",
        "studio_opened",
        "first_generation",
        "generate_clicked",
    }
)


def _pct(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * part / total, 1)


async def record_funnel_event(
    session: AsyncSession,
    *,
    user: User,
    event: str,
    meta: dict | None = None,
) -> None:
    if event not in ALLOWED_FUNNEL_EVENTS:
        return
    oid = workspace_owner_id(user)
    payload = json.dumps(meta, ensure_ascii=False) if meta else None
    session.add(
        FunnelEvent(
            owner_id=oid,
            user_id=user.id,
            event=event,
            meta=payload,
        )
    )


async def owner_has_funnel_event(session: AsyncSession, owner_id: int, event: str) -> bool:
    row = await session.scalar(
        select(FunnelEvent.id)
        .where(FunnelEvent.owner_id == owner_id, FunnelEvent.event == event)
        .limit(1)
    )
    return row is not None


async def record_funnel_event_once(
    session: AsyncSession,
    *,
    user: User,
    event: str,
    meta: dict | None = None,
) -> bool:
    """Записать событие, если для owner ещё не было такого event. True если записали."""
    if event not in ALLOWED_FUNNEL_EVENTS:
        return False
    oid = workspace_owner_id(user)
    if await owner_has_funnel_event(session, oid, event):
        return False
    await record_funnel_event(session, user=user, event=event, meta=meta)
    return True


async def record_funnel_event_for_owner_once(
    session: AsyncSession,
    *,
    owner_id: int,
    event: str,
    meta: dict | None = None,
) -> bool:
    if event not in ALLOWED_FUNNEL_EVENTS:
        return False
    if await owner_has_funnel_event(session, owner_id, event):
        return False
    owner = await session.get(User, owner_id)
    if not owner:
        return False
    await record_funnel_event(session, user=owner, event=event, meta=meta)
    return True


async def _owners_with_ws_key(session: AsyncSession, owner_ids: set[int]) -> set[int]:
    if not owner_ids:
        return set()
    rows = (
        await session.execute(
            select(WavespeedConnection.user_id).where(
                WavespeedConnection.user_id.in_(owner_ids)
            )
        )
    ).all()
    return {int(r[0]) for r in rows if r[0] is not None}


async def _owners_with_model(session: AsyncSession, owner_ids: set[int]) -> set[int]:
    if not owner_ids:
        return set()
    rows = (
        await session.execute(
            select(UserStudioModel.user_id).where(UserStudioModel.user_id.in_(owner_ids))
        )
    ).all()
    return {int(r[0]) for r in rows if r[0] is not None}


async def _owners_with_generation(session: AsyncSession, owner_ids: set[int]) -> set[int]:
    """
    Владельцы из когорты, у которых была хотя бы одна студийная генерация.
    Источники: studio_generations, funnel_events, usage (списание за генерацию).
    """
    if not owner_ids:
        return set()
    found: set[int] = set()
    gen_rows = (
        await session.execute(
            select(StudioGeneration.user_id).where(StudioGeneration.user_id.in_(owner_ids))
        )
    ).all()
    found.update(int(r[0]) for r in gen_rows if r[0] is not None)

    ev_rows = (
        await session.execute(
            select(FunnelEvent.owner_id).where(
                FunnelEvent.owner_id.in_(owner_ids),
                FunnelEvent.event.in_(tuple(_FIRST_GENERATION_FUNNEL_EVENTS)),
            )
        )
    ).all()
    found.update(int(r[0]) for r in ev_rows if r[0] is not None)

    usage_rows = (
        await session.execute(
            select(UsageEvent.user_id).where(
                UsageEvent.user_id.in_(owner_ids),
                UsageEvent.kind.in_(tuple(_STUDIO_GENERATION_USAGE_KINDS)),
            )
        )
    ).all()
    found.update(int(r[0]) for r in usage_rows if r[0] is not None)
    return found


async def _owners_opened_wizard(session: AsyncSession, owner_ids: set[int]) -> set[int]:
    if not owner_ids:
        return set()
    rows = (
        await session.execute(
            select(FunnelEvent.owner_id).where(
                FunnelEvent.owner_id.in_(owner_ids),
                FunnelEvent.event.in_(
                    (
                        "onboarding_wizard_opened",
                        "onboarding_wizard_completed",
                        "onboarding_generation_success",
                    )
                ),
            )
        )
    ).all()
    return {int(r[0]) for r in rows if r[0] is not None}


async def build_activation_funnel(session: AsyncSession, *, days: int = 30) -> dict:
    """
    Когорта владельцев, зарегистрировавшихся за N дней → шаги активации.
    Часть шагов из БД (ретроактивно), часть из funnel_events.
    """
    days = max(7, min(90, days))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    reg_rows = (
        await session.execute(
            select(User.id, User.created_at).where(
                User.parent_user_id.is_(None),
                User.created_at >= since,
            )
        )
    ).all()
    owner_ids = {int(r[0]) for r in reg_rows if r[0] is not None}
    registered = len(owner_ids)
    if registered == 0:
        return {
            "days": days,
            "registered": 0,
            "steps": [],
        }

    ws_ids = await _owners_with_ws_key(session, owner_ids)
    model_ids = await _owners_with_model(session, owner_ids)
    gen_ids = await _owners_with_generation(session, owner_ids)
    wizard_ids = await _owners_opened_wizard(session, owner_ids)

    event_counts: dict[str, int] = {}
    ev_rows = (
        await session.execute(
            select(FunnelEvent.event, func.count(func.distinct(FunnelEvent.owner_id)))
            .where(
                FunnelEvent.owner_id.in_(owner_ids),
            )
            .group_by(FunnelEvent.event)
        )
    ).all()
    for ev, cnt in ev_rows:
        event_counts[str(ev)] = int(cnt or 0)

    steps = [
        {
            "key": "registered",
            "label": "Регистрация",
            "count": registered,
            "pct_of_registered": 100.0,
        },
        {
            "key": "wizard_opened",
            "label": "Открыли wizard первой картинки",
            "count": len(wizard_ids),
            "pct_of_registered": _pct(len(wizard_ids), registered),
        },
        {
            "key": "ws_key",
            "label": "Ключ WaveSpeed сохранён",
            "count": len(ws_ids),
            "pct_of_registered": _pct(len(ws_ids), registered),
        },
        {
            "key": "model",
            "label": "Создана модель",
            "count": len(model_ids),
            "pct_of_registered": _pct(len(model_ids), registered),
        },
        {
            "key": "first_generation",
            "label": "Первая генерация в студии (когорта за период)",
            "count": len(gen_ids),
            "pct_of_registered": _pct(len(gen_ids), registered),
        },
    ]

    return {
        "days": days,
        "registered": registered,
        "steps": steps,
        "events_by_name": event_counts,
    }
