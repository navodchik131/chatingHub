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


def test_companion_persona_format():
    from app.services.companion_bot.persona import (
        CompanionPersona,
        format_companion_persona_block,
        parse_companion_persona,
    )

    raw = '{"age": "24", "city": "Barcelona", "hobbies": "yoga"}'
    p = parse_companion_persona(raw)
    assert p.age == "24"
    assert p.city == "Barcelona"
    block = format_companion_persona_block(name="Luna", profile_text="blonde", persona=p)
    assert "Age: 24" in block
    assert "Lives in: Barcelona" in block
    assert "Hobbies: yoga" in block


def test_companion_prompt_initiative():
    from datetime import datetime, timezone

    from app.services.companion_bot.persona import CompanionPersona
    from app.services.companion_bot.prompt import (
        PROMPT_VERSION,
        _message_text_for_transcript,
        build_companion_system_prompt,
        build_companion_user_prompt,
    )

    assert PROMPT_VERSION == "v3"

    out_msg = Message(
        id=2,
        conversation_id=1,
        direction=MessageDirection.outbound,
        text_original="Лежу в кровати",
        text_translated="Just chilling in bed",
    )
    assert _message_text_for_transcript(out_msg) == "Just chilling in bed"

    in_msg = Message(
        id=1,
        conversation_id=1,
        direction=MessageDirection.inbound,
        text_original="Hello Mia",
        text_translated="Привет Мия",
    )
    assert _message_text_for_transcript(in_msg) == "Hello Mia"

    now = datetime.now(timezone.utc)
    messages = [
        Message(
            id=1,
            conversation_id=1,
            direction=MessageDirection.inbound,
            text_original="бесишь",
            created_at=now,
        ),
        Message(
            id=2,
            conversation_id=1,
            direction=MessageDirection.outbound,
            text_original="ок",
            text_translated="sorry!",
            created_at=now,
        ),
        Message(
            id=3,
            conversation_id=1,
            direction=MessageDirection.inbound,
            text_original="Hello Mia",
            created_at=now,
        ),
    ]
    conv = SimpleNamespace(user_display_name="Renat")
    sys = build_companion_system_prompt(
        persona_name="Mia",
        persona_profile="",
        persona=CompanionPersona(city="Madrid"),
        target_lang="en",
        relationship_score=40,
        mood="playful",
        notes=[],
        messages=messages,
    )
    assert "MID-CONVERSATION" in sys
    assert "hello again" in sys.lower() or "ALREADY chatting" in sys

    user = build_companion_user_prompt(conv=conv, messages=messages)
    assert "Hello Mia" in user
    assert "no reset" in user.lower() or "Continue" in user
