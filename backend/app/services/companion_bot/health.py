"""Диагностика companion bot: почему бот молчит."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    BotResponseEvent,
    BotResponseEventStatus,
    CompanionConversationState,
    CompanionJob,
    CompanionJobStatus,
    Conversation,
    Message,
    MessageDirection,
)
from app.services.companion_bot.config import get_companion_config_for_conversation


async def diagnose_companion_health(
    session: AsyncSession,
    *,
    conv: Conversation,
    owner_id: int,
) -> dict:
    reasons: list[str] = []
    cfg = await get_companion_config_for_conversation(session, conv, owner_id=owner_id)

    if conv.is_blocked:
        reasons.append("Диалог заблокирован — входящие игнорируются.")
    if not cfg:
        reasons.append("AI-компаньон выключен (режим off или нет активного подключения).")
    elif not cfg.studio_model_id:
        reasons.append("На подключении не назначена модель студии.")

    pending_jobs = int(
        await session.scalar(
            select(func.count())
            .select_from(CompanionJob)
            .where(
                CompanionJob.conversation_id == conv.id,
                CompanionJob.status.in_(
                    [CompanionJobStatus.pending, CompanionJobStatus.running]
                ),
            )
        )
        or 0
    )
    pending_drafts = int(
        await session.scalar(
            select(func.count())
            .select_from(BotResponseEvent)
            .where(
                BotResponseEvent.conversation_id == conv.id,
                BotResponseEvent.status == BotResponseEventStatus.draft,
            )
        )
        or 0
    )

    if pending_jobs:
        reasons.append(f"В очереди {pending_jobs} задач(а) — ответ скоро.")
    if pending_drafts and not pending_jobs:
        reasons.append(f"Есть {pending_drafts} черновик(ов) — проверьте режим draft/semi_auto.")

    since = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_sends = int(
        await session.scalar(
            select(func.count())
            .select_from(BotResponseEvent)
            .where(
                BotResponseEvent.conversation_id == conv.id,
                BotResponseEvent.status == BotResponseEventStatus.sent,
                BotResponseEvent.sent_at >= since,
            )
        )
        or 0
    )
    if cfg and recent_sends >= cfg.max_replies_per_hour:
        reasons.append("Достигнут лимит ответов в час на подключении.")

    last_inbound = await session.scalar(
        select(Message.created_at)
        .where(
            Message.conversation_id == conv.id,
            Message.direction == MessageDirection.inbound,
        )
        .order_by(Message.id.desc())
        .limit(1)
    )
    last_sent = await session.scalar(
        select(BotResponseEvent.sent_at)
        .where(
            BotResponseEvent.conversation_id == conv.id,
            BotResponseEvent.status == BotResponseEventStatus.sent,
        )
        .order_by(BotResponseEvent.sent_at.desc())
        .limit(1)
    )

    state = await session.get(CompanionConversationState, conv.id)

    if not reasons:
        if pending_jobs:
            status = "waiting"
        elif cfg and cfg.mode.value == "draft":
            status = "draft_only"
        else:
            status = "ok"
    elif conv.is_blocked or not cfg:
        status = "blocked"
    elif pending_jobs or pending_drafts:
        status = "waiting"
    else:
        status = "blocked"

    return {
        "active": cfg is not None and not conv.is_blocked,
        "effective_mode": cfg.mode.value if cfg else None,
        "status": status,
        "reasons": reasons,
        "pending_jobs": pending_jobs,
        "pending_drafts": pending_drafts,
        "relationship_score": int(state.relationship_score) if state else None,
        "mood": state.mood if state else None,
        "last_inbound_at": last_inbound,
        "last_sent_at": last_sent,
    }
