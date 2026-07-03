"""Когда отвечать reply-to на конкретное сообщение, а когда слать обычным текстом."""

from __future__ import annotations

import random
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message, MessageDirection
from app.db.repo import list_messages
from app.services.companion_bot.prompt import (
    ThreadSignals,
    analyze_thread_signals,
    fan_asks_direct_factual,
)

_QUESTION_MARK_RE = re.compile(r"[?？]")
_DIRECT_ADDRESS_RE = re.compile(
    r"^(you|u|ты|тебя|тебе|mia|мия|babe|baby|hun|love)\b",
    re.IGNORECASE,
)


def should_use_reply_to(
    *,
    trigger: Message | None,
    followup: bool,
    signals: ThreadSignals,
    now: datetime | None = None,
) -> bool:
    if followup:
        return False
    if not trigger or trigger.direction != MessageDirection.inbound:
        return False

    text = (trigger.text_original or trigger.text_translated or "").strip()
    has_image = bool(getattr(trigger, "attachments", None))

    if signals.trust_repair or signals.direct_factual or signals.factual_pressure:
        return True
    if fan_asks_direct_factual(text):
        return True
    if has_image and text:
        return True
    if _QUESTION_MARK_RE.search(text):
        if signals.casual_checkin:
            return random.random() < 0.45
        return random.random() < 0.75

    created = trigger.created_at
    if created:
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age = (now or datetime.now(timezone.utc)) - created
        if age <= timedelta(minutes=12):
            if len(text) <= 40 and _DIRECT_ADDRESS_RE.search(text):
                return random.random() < 0.4
            return random.random() < 0.28
        if age <= timedelta(minutes=45):
            return random.random() < 0.15

    return False


async def resolve_reply_to_message_id(
    session: AsyncSession,
    *,
    owner_user_id: int,
    conv: Conversation,
    trigger_message_id: int,
    followup: bool = False,
) -> int | None:
    trigger = await session.get(Message, trigger_message_id)
    if not trigger or trigger.conversation_id != conv.id:
        return None

    if followup or trigger.direction == MessageDirection.outbound:
        return None

    history = await list_messages(session, conv.id, owner_user_id, limit=30)
    signals = analyze_thread_signals(history)
    if should_use_reply_to(trigger=trigger, followup=followup, signals=signals):
        return trigger_message_id
    return None
