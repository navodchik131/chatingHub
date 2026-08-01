"""Tests for bootstrap demo billing."""

from __future__ import annotations

import pytest

from app.services.demo_generations import (
    DEMO_ELIGIBLE_USAGE_KINDS,
    demo_slot_reserved_from_params,
    demo_slot_released_from_params,
)


def test_bootstrap_usage_kinds_are_demo_eligible() -> None:
    assert "studio_model_bootstrap_face_merge" in DEMO_ELIGIBLE_USAGE_KINDS
    assert "studio_model_bootstrap_body_compose" in DEMO_ELIGIBLE_USAGE_KINDS
    assert "studio_model_bootstrap_sheet" in DEMO_ELIGIBLE_USAGE_KINDS


def test_demo_slot_reserved_from_params() -> None:
    assert demo_slot_reserved_from_params({"demo_slot_reserved": "1"})
    assert demo_slot_reserved_from_params({"demo_slot_reserved": "true"})
    assert not demo_slot_reserved_from_params({})
    assert not demo_slot_reserved_from_params({"demo_slot_reserved": "0"})


def test_demo_slot_released_from_params() -> None:
    assert demo_slot_released_from_params({"demo_slot_released": "yes"})
    assert not demo_slot_released_from_params({"demo_slot_reserved": "1"})


def test_parse_mobile_auth_start_param() -> None:
    from app.services.telegram_mobile_auth import parse_mobile_auth_start_param

    assert parse_mobile_auth_start_param("mm_abc123") == "abc123"
    assert parse_mobile_auth_start_param("hello") is None
    assert parse_mobile_auth_start_param(None) is None
