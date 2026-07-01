"""Категории диалогов: ручные (VIP, Бомж) и автоматические (новые, без ответа)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.models import Conversation, Message, MessageDirection

NO_RESPONSE_AFTER = timedelta(hours=24)

MANUAL_CATEGORIES = frozenset({"vip", "bomzh"})


def normalize_manual_category(raw: object) -> str | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    s = raw.strip().lower()
    if not s or s == "none":
        return None
    if s not in MANUAL_CATEGORIES:
        raise ValueError(f"invalid manual_category: {s}")
    return s


def is_no_response(last_message: Message | None, *, now: datetime | None = None) -> bool:
    """Последнее сообщение входящее и без ответа оператора/бота более 24 ч."""
    if not last_message or last_message.direction != MessageDirection.inbound:
        return False
    ts = now or datetime.now(timezone.utc)
    created = last_message.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return ts - created >= NO_RESPONSE_AFTER


def is_new_conversation(
    conv: Conversation,
    *,
    has_outbound: bool,
    now: datetime | None = None,
) -> bool:
    """Новый диалог: оператор или бот ещё ни разу не отвечали."""
    del conv, now
    return not has_outbound


def conversation_category_flags(
    conv: Conversation,
    *,
    last_message: Message | None,
    has_outbound: bool,
    now: datetime | None = None,
) -> dict[str, bool]:
    return {
        "is_no_response": is_no_response(last_message, now=now),
        "is_new": is_new_conversation(conv, has_outbound=has_outbound, now=now),
    }
