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


def test_companion_prompt_v4_chatter():
    from datetime import datetime, timezone

    from app.services.companion_bot.persona import CompanionPersona
    from app.services.companion_bot.prompt import (
        PROMPT_VERSION,
        _message_text_for_transcript,
        build_companion_system_prompt,
        build_companion_user_prompt,
        recent_outbound_texts,
        reply_too_similar_to_recent,
    )

    assert PROMPT_VERSION == "v4-chatter-vision-casual"

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
    assert "senior" in sys.lower() or "chatter" in sys.lower()
    assert "ACTIVE THREAD" in sys
    assert "mid-chat" in sys.lower()
    assert "casual human texting" in sys.lower()
    assert "mirror the fan" in sys.lower()

    user = build_companion_user_prompt(conv=conv, messages=messages)
    assert "Hello Mia" in user
    assert "no reset" in user.lower() or "repeated beats" in user.lower()

    recent = recent_outbound_texts(messages, limit=4)
    assert recent == ["sorry!"]
    assert reply_too_similar_to_recent("sorry!", recent) is True
    assert reply_too_similar_to_recent("totally different topic here", recent) is False


def test_companion_prompt_image_description_block():
    from app.services.companion_bot.prompt import build_companion_user_prompt

    conv = SimpleNamespace(user_display_name="Renat")
    messages = [
        Message(
            id=1,
            conversation_id=1,
            direction=MessageDirection.inbound,
            text_original="look at this",
        ),
    ]
    trigger = messages[0]
    user = build_companion_user_prompt(
        conv=conv,
        messages=messages,
        fan_image_description="Fan selfie at the beach, sunset, casual smile.",
        trigger_message=trigger,
    )
    assert "INTERNAL note for you only" in user
    assert "do not quote" in user.lower()
    assert "beach" in user
    assert "look at this" in user


def test_read_vision_description_from_meta():
    import json

    from app.services.companion_bot.vision import VISION_META_KEY, read_vision_description

    meta = json.dumps({VISION_META_KEY: "A dog on a sofa"})
    assert read_vision_description(meta) == "A dog on a sofa"
    assert read_vision_description(None) is None
