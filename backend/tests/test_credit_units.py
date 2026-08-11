import pytest

from app.services.credit_units import CREDITS_PER_USD, credits_to_usd, legacy_to_cent_credits, usd_to_credits


def test_usd_to_credits_cent_model():
    assert usd_to_credits(0.126, markup_usd=0.002) == 13
    assert usd_to_credits(0.42, markup_usd=0.002) == 43


def test_credits_to_usd():
    assert credits_to_usd(100) == 1.0


def test_legacy_migration_factor():
    # 300 old credits @ 2.97 RUB, CBR 90 → 990 cent-credits
    out = legacy_to_cent_credits(300, old_rub_per_credit=2.97, cbr_rub_per_usd=90.0)
    assert out == 990


def test_minimum_one_credit():
    assert usd_to_credits(0.001, markup_usd=0.0) == 1
