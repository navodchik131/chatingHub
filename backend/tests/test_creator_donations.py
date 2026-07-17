"""Tests for platform creator donations."""

from __future__ import annotations

import pytest

from app.services.creator_donation_apply import _donation_request_id
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
