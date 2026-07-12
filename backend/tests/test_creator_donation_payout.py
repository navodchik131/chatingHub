"""Tests for creator donation payouts."""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.creator_donation_payout import (
    calc_platform_fee,
    donation_available_at,
    is_donation_available,
    payout_asset_by_id,
)


def test_calc_platform_fee() -> None:
    fee, net = calc_platform_fee(10_000)
    assert fee == 200
    assert net == 9800


def test_donation_available_at_first_half() -> None:
    dt = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
    assert donation_available_at(dt) == datetime(2026, 3, 16, tzinfo=timezone.utc)


def test_donation_available_at_second_half() -> None:
    dt = datetime(2026, 3, 20, tzinfo=timezone.utc)
    assert donation_available_at(dt) == datetime(2026, 4, 1, tzinfo=timezone.utc)


def test_is_donation_available() -> None:
    occurred = datetime(2026, 3, 10, tzinfo=timezone.utc)
    before = datetime(2026, 3, 15, tzinfo=timezone.utc)
    after = datetime(2026, 3, 16, tzinfo=timezone.utc)
    assert not is_donation_available(occurred, now=before)
    assert is_donation_available(occurred, now=after)


def test_payout_asset_by_id() -> None:
    asset = payout_asset_by_id("USDT_TRC20")
    assert asset is not None
    assert asset["payout_currency"] == "USDT"
    assert asset["network"] == "TRC20"
    assert payout_asset_by_id("INVALID") is None
