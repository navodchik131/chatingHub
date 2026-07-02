"""Tests for Tribute webhook ingest and earnings split."""

from __future__ import annotations

import pytest

from app.connectors.tribute.handlers import _amount_minor_from_payload, _norm_event_name
from app.services.tribute_earnings import chatter_share_ratio


def test_norm_event_name() -> None:
    assert _norm_event_name("new_donation") == "newdonation"
    assert _norm_event_name("NewDonation") == "newdonation"


def test_amount_minor_from_payload() -> None:
    assert _amount_minor_from_payload({"amount": 500, "currency": "usd"}, event_name="newdonation") == 500
    assert _amount_minor_from_payload({"amount": 9.99, "currency": "eur"}, event_name="x") == 999


def test_chatter_share_ratio_default() -> None:
    assert chatter_share_ratio() == 0.2
