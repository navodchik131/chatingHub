"""Unit-тесты планировщика медиа companion bot."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.companion_bot.media_planner import (
    build_media_llm_hint,
    build_media_search_query,
    choose_media_action,
    detect_fan_media_request,
    format_usd_price,
)
from app.services.companion_bot.prompt import analyze_thread_signals


def _msg(direction: str, text: str) -> SimpleNamespace:
    from app.db.models import MessageDirection

    d = MessageDirection.inbound if direction == "in" else MessageDirection.outbound
    return SimpleNamespace(
        direction=d,
        text_original=text,
        text_translated=text,
        created_at=None,
    )


def test_detect_fan_media_request_ru_en() -> None:
    assert detect_fan_media_request("скинь фотку") is True
    assert detect_fan_media_request("send me a selfie") is True
    assert detect_fan_media_request("how are you") is False


def test_choose_media_action_fan_asked_free() -> None:
    signals = analyze_thread_signals([_msg("in", "show me a pic")])
    action, reason = choose_media_action(
        fan_asked=True,
        explicit_ask=False,
        relationship_score=50,
        signals=signals,
        followup=False,
        manual_category=None,
        recent_media_sends_24h=0,
        outbound_since_last_media=5,
        has_free=True,
        has_teaser=True,
        has_paid=True,
        matched_tier="free",
        recent_donation_usd_cents=0,
        asset_price_usd_cents=0,
    )
    assert action == "send_free"
    assert reason == "fan_asked_free_match"


def test_choose_media_action_paid_offer() -> None:
    signals = analyze_thread_signals([_msg("in", "send nudes")])
    action, _ = choose_media_action(
        fan_asked=True,
        explicit_ask=True,
        relationship_score=70,
        signals=signals,
        followup=False,
        manual_category=None,
        recent_media_sends_24h=0,
        outbound_since_last_media=2,
        has_free=False,
        has_teaser=True,
        has_paid=True,
        matched_tier="paid",
        recent_donation_usd_cents=0,
        asset_price_usd_cents=450,
    )
    assert action == "offer_paid"


def test_choose_media_action_paid_unlock_after_donation() -> None:
    signals = analyze_thread_signals([_msg("in", "where is my pic")])
    action, reason = choose_media_action(
        fan_asked=True,
        explicit_ask=False,
        relationship_score=60,
        signals=signals,
        followup=False,
        manual_category=None,
        recent_media_sends_24h=0,
        outbound_since_last_media=1,
        has_free=False,
        has_teaser=False,
        has_paid=True,
        matched_tier="paid",
        recent_donation_usd_cents=500,
        asset_price_usd_cents=450,
    )
    assert action == "send_paid_unlocked"
    assert reason == "fan_paid_recently"


def test_choose_media_action_no_content_deflect() -> None:
    signals = analyze_thread_signals([_msg("in", "photo please")])
    action, reason = choose_media_action(
        fan_asked=True,
        explicit_ask=False,
        relationship_score=40,
        signals=signals,
        followup=False,
        manual_category=None,
        recent_media_sends_24h=0,
        outbound_since_last_media=0,
        has_free=False,
        has_teaser=False,
        has_paid=False,
        matched_tier=None,
        recent_donation_usd_cents=0,
        asset_price_usd_cents=0,
    )
    assert action == "deflect_no_content"
    assert reason == "fan_asked_no_match"


def test_choose_media_action_proactive_teaser() -> None:
    messages = [_msg("in", "hey"), _msg("out", "hi"), _msg("in", "cool vibe")]
    signals = analyze_thread_signals(messages)
    action, reason = choose_media_action(
        fan_asked=False,
        explicit_ask=False,
        relationship_score=60,
        signals=signals,
        followup=False,
        manual_category=None,
        recent_media_sends_24h=0,
        outbound_since_last_media=5,
        has_free=True,
        has_teaser=True,
        has_paid=True,
        matched_tier="teaser",
        recent_donation_usd_cents=0,
        asset_price_usd_cents=0,
    )
    assert action == "send_teaser"
    assert reason == "proactive_teaser_warm"


def test_choose_media_action_skip_on_factual() -> None:
    signals = analyze_thread_signals([_msg("in", "который час?")])
    action, reason = choose_media_action(
        fan_asked=False,
        explicit_ask=False,
        relationship_score=80,
        signals=signals,
        followup=False,
        manual_category=None,
        recent_media_sends_24h=0,
        outbound_since_last_media=10,
        has_free=True,
        has_teaser=True,
        has_paid=True,
        matched_tier="free",
        recent_donation_usd_cents=0,
        asset_price_usd_cents=0,
    )
    assert action == "none"
    assert reason == "factual_qa_no_media"


def test_build_media_search_query_from_fan_text() -> None:
    messages = [_msg("in", "got any gym pics?")]
    signals = analyze_thread_signals(messages)
    q = build_media_search_query(messages=messages, signals=signals, followup=False)
    assert "gym" in q.lower()


def test_build_media_llm_hint_send_teaser() -> None:
    from app.services.companion_bot.media_planner import MediaPlan

    hint = build_media_llm_hint(MediaPlan(action="send_teaser"))
    assert "WILL send" in hint


def test_format_usd_price() -> None:
    assert format_usd_price(450) == "$4.50"
    assert format_usd_price(0) == "$0.00"
