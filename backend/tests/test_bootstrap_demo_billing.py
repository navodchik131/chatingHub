"""Tests for bootstrap demo billing."""

from __future__ import annotations

import pytest

from app.services.demo_generations import (
    DEMO_ELIGIBLE_USAGE_KINDS,
    demo_slot_reserved_from_params,
    demo_slot_released_from_params,
    effective_demo_remaining_for_access,
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


def test_effective_demo_remaining_for_access() -> None:
    assert effective_demo_remaining_for_access(0, demo_slot_reserved=False) == 0
    assert effective_demo_remaining_for_access(1, demo_slot_reserved=False) == 1
    assert effective_demo_remaining_for_access(0, demo_slot_reserved=True) == 1
    assert effective_demo_remaining_for_access(2, demo_slot_reserved=True) == 2


def test_parse_mobile_auth_start_param() -> None:
    from app.services.telegram_mobile_auth import (
        parse_mobile_auth_start_param,
        parse_mobile_link_start_param,
    )

    assert parse_mobile_auth_start_param("mm_abc123") == "abc123"
    assert parse_mobile_auth_start_param("mml_abc123") is None
    assert parse_mobile_link_start_param("mml_abc123") == "abc123"
    assert parse_mobile_link_start_param("mm_abc123") is None
    assert parse_mobile_auth_start_param("hello") is None
    assert parse_mobile_auth_start_param(None) is None
