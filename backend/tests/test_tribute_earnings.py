"""Tests for Tribute webhook ingest and earnings split."""

from __future__ import annotations

import pytest

from app.connectors.tribute.handlers import _amount_minor_from_payload, _norm_event_name
from app.db.models import User
from app.services.tribute_member_share import (
    default_tribute_share_percent,
    member_tribute_share_ratio,
    resolve_member_tribute_share_percent,
)


def test_norm_event_name() -> None:
    assert _norm_event_name("new_donation") == "newdonation"
    assert _norm_event_name("NewDonation") == "newdonation"


def test_amount_minor_from_payload() -> None:
    assert _amount_minor_from_payload({"amount": 500, "currency": "usd"}, event_name="newdonation") == 500
    assert _amount_minor_from_payload({"amount": 9.99, "currency": "eur"}, event_name="x") == 999


def test_default_tribute_share_percent() -> None:
    assert default_tribute_share_percent() == 20


def test_member_tribute_share_ratio_uses_profile() -> None:
    member = User(parent_user_id=1, tribute_share_percent=35)
    assert resolve_member_tribute_share_percent(member) == 35
    assert member_tribute_share_ratio(member) == 0.35


def test_member_tribute_share_ratio_fallback() -> None:
    member = User(parent_user_id=1, tribute_share_percent=None)
    assert resolve_member_tribute_share_percent(member) == 20
    assert member_tribute_share_ratio(member) == 0.2
