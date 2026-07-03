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

    assert PROMPT_VERSION == "v6-chatter-goals-rag-1"

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
    assert "CHATTER GOALS" in sys
    assert "RETENTION" in sys
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


def test_persona_local_time_utc_plus_3():
    from datetime import datetime, timedelta, timezone

    from app.services.companion_bot.persona import CompanionPersona
    from app.services.companion_bot.prompt import parse_persona_utc_offset, persona_local_time_block

    assert parse_persona_utc_offset("UTC+3") == timezone(timedelta(hours=3))
    block = persona_local_time_block(
        CompanionPersona(timezone="UTC+3"),
        now=datetime(2026, 6, 29, 9, 30, tzinfo=timezone.utc),
    )
    assert "12:30" in block
    assert "never UTC" in block.lower() or "never utc" in block.lower()


def test_direct_factual_and_complaint_signals():
    from datetime import datetime, timezone

    from app.services.companion_bot.prompt import (
        analyze_thread_signals,
        build_companion_user_prompt,
        fan_asks_direct_factual,
    )

    assert fan_asks_direct_factual("А время сколько у тебя сейчас?")
    assert fan_asks_direct_factual("со скольки ты работаешь в итоге")
    now = datetime.now(timezone.utc)
    messages = [
        Message(
            id=1,
            conversation_id=1,
            direction=MessageDirection.inbound,
            text_original="со скольки ты работаешь?",
            created_at=now,
        ),
        Message(
            id=2,
            conversation_id=1,
            direction=MessageDirection.outbound,
            text_original="с 11 до 7 сегодня",
            created_at=now,
        ),
        Message(
            id=3,
            conversation_id=1,
            direction=MessageDirection.inbound,
            text_original="Ты щас как бот общаешься",
            created_at=now,
        ),
    ]
    sig = analyze_thread_signals(messages)
    assert sig.fan_complaint is True
    assert sig.trust_repair is True
    assert sig.direct_factual is True
    conv = SimpleNamespace(user_display_name="Renat")
    user = build_companion_user_prompt(conv=conv, messages=messages)
    assert "DIRECT ANSWER REQUIRED" in user
    assert "TRUST REPAIR" in user


def test_casual_checkin_skips_direct_mode_and_trust_repair():
    from datetime import datetime, timezone

    from app.services.companion_bot.prompt import (
        analyze_thread_signals,
        build_companion_user_prompt,
    )

    now = datetime.now(timezone.utc)
    messages = [
        Message(
            id=1,
            conversation_id=1,
            direction=MessageDirection.inbound,
            text_original="Ты щас как бот общаешься",
            created_at=now,
        ),
        Message(
            id=2,
            conversation_id=1,
            direction=MessageDirection.outbound,
            text_original="Renat, с 9 работаю, извини",
            created_at=now,
        ),
        Message(
            id=3,
            conversation_id=1,
            direction=MessageDirection.inbound,
            text_original="что делаешь?",
            created_at=now,
        ),
    ]
    sig = analyze_thread_signals(messages)
    assert sig.casual_checkin is True
    assert sig.trust_repair is False
    assert sig.direct_factual is False
    conv = SimpleNamespace(user_display_name="Renat")
    user = build_companion_user_prompt(conv=conv, messages=messages)
    assert "CASUAL CHECK-IN" in user
    assert "TRUST REPAIR" not in user
    assert "DIRECT ANSWER REQUIRED" not in user


def test_reply_over_reports_on_checkin():
    from app.services.companion_bot.prompt import reply_over_reports_on_checkin

    assert reply_over_reports_on_checkin(
        "Сейчас 12:22, опаздываю на работу, график с 9 до 6",
        casual_checkin=True,
    )
    assert reply_over_reports_on_checkin(
        "Я не бот, просто работаю по графику",
        casual_checkin=True,
    )
    assert not reply_over_reports_on_checkin(
        "Дома, кофе пью 😌",
        casual_checkin=True,
    )
    assert not reply_over_reports_on_checkin(
        "Сейчас 12:22, опаздываю на работу",
        casual_checkin=False,
    )


def test_transcript_uses_persona_local_time():
    from datetime import datetime, timezone

    from app.services.companion_bot.persona import CompanionPersona
    from app.services.companion_bot.prompt import _format_transcript

    msg = Message(
        id=1,
        conversation_id=1,
        direction=MessageDirection.inbound,
        text_original="привет",
        created_at=datetime(2026, 6, 29, 11, 22, tzinfo=timezone.utc),
    )
    text = _format_transcript(
        [msg],
        "Renat",
        persona=CompanionPersona(timezone="UTC+3"),
    )
    assert "14:22" in text
    assert "character-local" in text.lower()


def test_canon_block_in_system_prompt():
    from app.services.companion_bot.persona import CompanionPersona
    from app.services.companion_bot.prompt import build_companion_system_prompt

    sys = build_companion_system_prompt(
        persona_name="Mia",
        persona_profile="",
        persona=CompanionPersona(
            city="Кишинев",
            timezone="UTC+3",
            lifestyle="Работает программистом, офис, с 9 до 18.",
        ),
        target_lang="ru",
        relationship_score=50,
        mood="playful",
        notes=[],
        messages=[],
    )
    assert "CANON FACTS" in sys
    assert "9" in sys and "18" in sys
    assert "Character local time" in sys
    assert "график сдвинулся" in sys


def test_trailing_hook_similarity():
    from app.services.companion_bot.prompt import reply_too_similar_to_recent

    recent = ["Ха, ладно. А ты в зале уже разогрелся?"]
    cand = "Renat, с 9 работаю. А с напряжением в зале что?"
    assert reply_too_similar_to_recent(cand, recent) is True


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


def test_reply_target_direct_question():
    from datetime import datetime, timezone

    from app.db.models import Message, MessageDirection
    from app.services.companion_bot.prompt import analyze_thread_signals
    from app.services.companion_bot.reply_target import should_use_reply_to

    now = datetime.now(timezone.utc)
    trigger = Message(
        id=1,
        conversation_id=1,
        direction=MessageDirection.inbound,
        text_original="который час у тебя?",
        created_at=now,
    )
    messages = [trigger]
    signals = analyze_thread_signals(messages)
    assert should_use_reply_to(trigger=trigger, followup=False, signals=signals, now=now) is True


def test_reply_target_followup_never_replies():
    from app.db.models import Message, MessageDirection
    from app.services.companion_bot.prompt import analyze_thread_signals
    from app.services.companion_bot.reply_target import should_use_reply_to

    trigger = Message(
        id=1,
        conversation_id=1,
        direction=MessageDirection.outbound,
        text_original="hey",
    )
    signals = analyze_thread_signals([])
    assert should_use_reply_to(trigger=trigger, followup=True, signals=signals) is False


def test_followup_unanswered_outbound_limit():
    import asyncio
    from datetime import datetime, timezone

    from app.db.models import Message, MessageDirection
    from app.services.companion_bot.orchestrator import _count_outbound_since_last_fan

    now = datetime.now(timezone.utc)
    messages = [
        Message(id=5, conversation_id=1, direction=MessageDirection.outbound, created_at=now),
        Message(id=4, conversation_id=1, direction=MessageDirection.outbound, created_at=now),
        Message(id=3, conversation_id=1, direction=MessageDirection.outbound, created_at=now),
        Message(id=2, conversation_id=1, direction=MessageDirection.outbound, created_at=now),
        Message(id=1, conversation_id=1, direction=MessageDirection.inbound, created_at=now),
    ]

    class _FakeSession:
        async def scalars(self, _q):
            class _R:
                def all(self_inner):
                    return messages

            return _R()

    count = asyncio.run(_count_outbound_since_last_fan(_FakeSession(), 1))
    assert count == 4


def test_style_extract_human_pair():
    from datetime import datetime, timezone

    from app.db.models import Conversation, Message, MessageDirection, Platform
    from app.services.companion_bot.style_extract import extract_pairs_from_messages

    now = datetime.now(timezone.utc)
    conv = Conversation(
        id=1,
        user_id=1,
        platform=Platform.telegram,
        external_chat_id="1",
        external_topic_id="0",
    )
    messages = [
        Message(
            id=1,
            conversation_id=1,
            direction=MessageDirection.inbound,
            text_original="привет, как дела?",
            created_at=now,
        ),
        Message(
            id=2,
            conversation_id=1,
            direction=MessageDirection.outbound,
            text_original="RU",
            text_translated="hey babe im good wbu",
            sender_user_id=42,
            created_at=now,
        ),
    ]
    pairs = extract_pairs_from_messages(messages, conv=conv, bot_ratings={})
    assert len(pairs) == 1
    assert pairs[0].fan_message == "привет, как дела?"
    assert pairs[0].model_reply == "hey babe im good wbu"
    assert pairs[0].is_human is True
    assert pairs[0].quality_score >= 2.0


def test_style_extract_skips_negative_bot():
    from datetime import datetime, timezone

    from app.db.models import Conversation, Message, MessageDirection, Platform
    from app.services.companion_bot.style_extract import extract_pairs_from_messages

    now = datetime.now(timezone.utc)
    conv = Conversation(
        id=1,
        user_id=1,
        platform=Platform.telegram,
        external_chat_id="1",
        external_topic_id="0",
    )
    messages = [
        Message(
            id=1,
            conversation_id=1,
            direction=MessageDirection.inbound,
            text_original="hello",
            created_at=now,
        ),
        Message(
            id=2,
            conversation_id=1,
            direction=MessageDirection.outbound,
            text_translated="bot reply",
            meta='{"companion_bot": true, "bot_response_event_id": 1}',
            created_at=now,
        ),
    ]
    pairs = extract_pairs_from_messages(messages, conv=conv, bot_ratings={2: -1})
    assert pairs == []


def test_style_rag_static_fallback():
    from app.services.companion_bot.style_rag import _load_static_examples, _pick_top

    static = list(_load_static_examples())
    assert static
    picked = _pick_top(
        fan_text="привет как дела",
        lang="ru",
        followup=False,
        candidates=static,
        limit=2,
    )
    assert len(picked) >= 1


def test_fan_tier_block_vip():
    from app.services.companion_bot.prompt import _fan_tier_block

    assert "VIP" in _fan_tier_block("vip")
    assert "low spender" in _fan_tier_block("bomzh")
    assert _fan_tier_block(None) == ""


def test_median_sla():
    from app.services.chatter_stats import _median

    assert _median([10, 20, 30]) == 20
    assert _median([10, 20]) == 15
    assert _median([]) is None


def test_state_update_mood():
    from app.services.companion_bot.state_update import _infer_mood

    assert _infer_mood("miss you ❤") == "warm"
    assert _infer_mood("just chilling") is None
