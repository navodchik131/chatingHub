"""Тесты воронки активации."""

from __future__ import annotations

from app.services.funnel_analytics import (
    ALLOWED_FUNNEL_EVENTS,
    _FIRST_GENERATION_FUNNEL_EVENTS,
    _STUDIO_GENERATION_USAGE_KINDS,
    _pct,
)


def test_allowed_funnel_events_include_onboarding():
    assert "signup" in ALLOWED_FUNNEL_EVENTS
    assert "onboarding_wizard_opened" in ALLOWED_FUNNEL_EVENTS
    assert "onboarding_ws_key_saved" in ALLOWED_FUNNEL_EVENTS
    assert "first_generation" in ALLOWED_FUNNEL_EVENTS


def test_pct_helper():
    assert _pct(0, 0) == 0.0
    assert _pct(5, 10) == 50.0


def test_first_generation_signal_sets_not_empty():
    assert "first_generation" in _FIRST_GENERATION_FUNNEL_EVENTS
    assert "onboarding_generation_success" in _FIRST_GENERATION_FUNNEL_EVENTS
    assert "studio_prompt_refine" in _STUDIO_GENERATION_USAGE_KINDS
