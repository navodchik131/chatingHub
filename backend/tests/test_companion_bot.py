"""Тесты companion bot."""

from __future__ import annotations

from types import SimpleNamespace

from app.db.models import CompanionBotMode, Message, MessageDirection
from app.services.companion_bot.config import (
    _parse_mode,
    _resolve_effective_mode,
)
from app.services.companion_bot.orchestrator import _semi_auto_allowed
from app.services.chat_messages import parse_companion_message_meta


def test_parse_companion_mode():
    assert _parse_mode("auto") == CompanionBotMode.auto
    assert _parse_mode("draft") == CompanionBotMode.draft
    assert _parse_mode("invalid") == CompanionBotMode.off


def test_conversation_override_beats_connection_off():
    conv = SimpleNamespace(companion_mode_override="auto")
    conn = SimpleNamespace(companion_mode="off")
    assert _resolve_effective_mode(conv, conn) == CompanionBotMode.auto


def test_conversation_force_off():
    conv = SimpleNamespace(companion_mode_override="off")
    conn = SimpleNamespace(companion_mode="auto")
    assert _resolve_effective_mode(conv, conn) == CompanionBotMode.off


def test_inherit_connection_mode():
    conv = SimpleNamespace(companion_mode_override=None)
    conn = SimpleNamespace(companion_mode="draft")
    assert _resolve_effective_mode(conv, conn) == CompanionBotMode.draft


def test_semi_auto_short_text():
    msg = Message(
        id=1,
        conversation_id=1,
        direction=MessageDirection.inbound,
        text_original="Hey, how are you?",
    )
    assert _semi_auto_allowed(trigger=msg, has_image=False) is True


def test_parse_companion_meta():
    ok, eid = parse_companion_message_meta(
        '{"companion_bot": true, "bot_response_event_id": 42}'
    )
    assert ok is True
    assert eid == 42
