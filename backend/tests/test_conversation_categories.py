"""Тесты категорий диалогов."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db.models import Conversation, Message, MessageDirection, Platform
from app.services.conversation_categories import (
    conversation_category_flags,
    is_new_conversation,
    is_no_response,
    normalize_manual_category,
)


def _msg(direction: MessageDirection, *, hours_ago: float = 0) -> Message:
    m = Message()
    m.direction = direction
    m.created_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return m


def _conv(*, days_ago: float = 0) -> Conversation:
    c = Conversation()
    c.platform = Platform.telegram
    c.created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return c


def test_normalize_manual_category() -> None:
    assert normalize_manual_category(None) is None
    assert normalize_manual_category("vip") == "vip"
    assert normalize_manual_category(" VIP ") == "vip"
    assert normalize_manual_category("none") is None
    with pytest.raises(ValueError):
        normalize_manual_category("unknown")


def test_is_no_response() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
    assert not is_no_response(None, now=now)
    assert not is_no_response(_msg(MessageDirection.outbound), now=now)
    recent = _msg(MessageDirection.inbound, hours_ago=1)
    assert not is_no_response(recent, now=now)
    old = _msg(MessageDirection.inbound, hours_ago=25)
    assert is_no_response(old, now=now)


def test_is_new_conversation() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
    conv = _conv(days_ago=30)
    assert is_new_conversation(conv, has_outbound=False, now=now)
    assert not is_new_conversation(conv, has_outbound=True, now=now)


def test_conversation_category_flags() -> None:
    now = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
    conv = _conv(days_ago=10)
    flags = conversation_category_flags(
        conv,
        last_message=_msg(MessageDirection.inbound, hours_ago=30),
        has_outbound=True,
        now=now,
    )
    assert flags["is_no_response"] is True
    assert flags["is_new"] is False
