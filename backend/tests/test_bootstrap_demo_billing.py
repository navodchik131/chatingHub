"""Tests for bootstrap demo billing."""

from __future__ import annotations

import pytest

from app.services.demo_generations import DEMO_ELIGIBLE_USAGE_KINDS


def test_bootstrap_usage_kinds_are_demo_eligible() -> None:
    assert "studio_model_bootstrap_face_merge" in DEMO_ELIGIBLE_USAGE_KINDS
    assert "studio_model_bootstrap_body_compose" in DEMO_ELIGIBLE_USAGE_KINDS
    assert "studio_model_bootstrap_sheet" in DEMO_ELIGIBLE_USAGE_KINDS


def test_parse_mobile_auth_start_param() -> None:
    from app.services.telegram_mobile_auth import parse_mobile_auth_start_param

    assert parse_mobile_auth_start_param("mm_abc123") == "abc123"
    assert parse_mobile_auth_start_param("hello") is None
    assert parse_mobile_auth_start_param(None) is None
