"""Tests for platform creator donations."""

from __future__ import annotations

import pytest

from app.services.creator_donation_apply import (
    _creator_donation_external_event_id,
    _donation_request_id,
)
from app.services.creator_donations import validate_min_amount_minor, normalize_donation_currency


def test_normalize_donation_currency() -> None:
    assert normalize_donation_currency("eur") == "EUR"
    with pytest.raises(Exception):
        normalize_donation_currency("GBP")


def test_validate_min_amount_minor_eur() -> None:
    validate_min_amount_minor("EUR", 100)
    with pytest.raises(Exception):
        validate_min_amount_minor("EUR", 50)


def test_donation_request_id_from_payload() -> None:
    payload = {"donation_request_id": 42, "telegram_user_id": 1}
    assert _donation_request_id(payload) == 42
    assert _donation_request_id({"donation": {"donationRequestId": 99}}) == 99
    assert _donation_request_id({"request_id": 77}) == 77
    assert _donation_request_id({"goal": {"donation_request_id": 55}}) == 55


def test_telegram_user_id_large() -> None:
    from app.services.creator_donation_apply import _telegram_user_id

    payload = {"telegram_user_id": 8353501632}
    assert _telegram_user_id(payload) == 8353501632


def test_creator_donation_external_event_id_differs_per_payment() -> None:
    base = {
        "name": "new_donation",
        "payload": {
            "donation_request_id": 188864,
            "amount": 10000,
            "currency": "rub",
            "telegram_user_id": 1,
        },
    }
    first = {**base, "sent_at": "2026-07-12T09:39:36.163088457Z"}
    second = {**base, "sent_at": "2026-07-17T11:04:48.000000000Z", "payload": {**base["payload"], "amount": 20000}}
    id1 = _creator_donation_external_event_id(first)
    id2 = _creator_donation_external_event_id(second)
    assert id1 != id2
    assert id1 != "creator_donation:0:new_donation:188864"
    assert id2 != "creator_donation:0:new_donation:188864"


def test_creator_donation_external_event_id_uses_payment_id() -> None:
    body = {
        "name": "new_donation",
        "payload": {"donation_id": 999, "donation_request_id": 188864},
    }
    assert _creator_donation_external_event_id(body) == "creator_donation:0:new_donation:999"
