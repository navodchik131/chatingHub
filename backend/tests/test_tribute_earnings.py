"""Tests for Tribute webhook ingest and earnings split."""

from __future__ import annotations

import pytest

from app.connectors.tribute.handlers import (
    _amount_minor_from_payload,
    _currency_from_payload,
    _event_kind,
    _external_event_id,
    _norm_event_name,
)
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
    assert _amount_minor_from_payload({"amount": 500.0, "currency": "usd"}, event_name="x") == 500
    assert (
        _amount_minor_from_payload(
            {"donation": {"amount": 1200, "currency": "rub"}},
            event_name="newdonation",
        )
        == 1200
    )


def test_amount_minor_from_goal_nested_payload() -> None:
    payload = {
        "goal": {"amount": 25000, "currency": "RUB"},
        "donation_request_id": 991,
        "telegram_user_id": 123,
    }
    assert _amount_minor_from_payload(payload, event_name="newdonation") == 25000
    assert _currency_from_payload(payload) == "RUB"


def test_amount_minor_from_subscription_price_field() -> None:
    payload = {
        "subscription_name": "VIP",
        "price": 9900,
        "currency": "RUB",
        "subscription_id": 42,
    }
    assert _amount_minor_from_payload(payload, event_name="newsubscription") == 9900


def test_event_kind_accepts_unknown_donation_like_events() -> None:
    payload = {"amount": 700, "currency": "USD"}
    assert _event_kind("newgoaldonation", payload) == "revenue"
    assert _event_kind("random_event", payload) is None


def test_external_event_id_uses_donation_request_id() -> None:
    body = {
        "name": "new_donation",
        "payload": {"donation_request_id": 555, "amount": 1000, "currency": "rub"},
    }
    assert _external_event_id(3, body) == "3:new_donation:555"


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
