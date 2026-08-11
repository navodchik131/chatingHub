from decimal import Decimal
from unittest.mock import patch

from app.config import settings
from app.services.billing_credits import (
    apply_purchase_bonus_credits,
    credits_total_rub,
    referrer_reward_credits_from_payment_rub,
    rub_to_credits_ceil,
)


def test_rub_to_credits_ceil_at_cbr_90():
    with patch("app.services.billing_credits.cached_cbr_rub_per_usd_sync", return_value=90.0):
        assert rub_to_credits_ceil(990) == 1100


def test_referrer_ten_percent_990_at_cbr_90():
    with patch("app.services.billing_credits.cached_cbr_rub_per_usd_sync", return_value=90.0):
        assert referrer_reward_credits_from_payment_rub(Decimal("990")) == 110


def test_credits_total_rub_500_at_cbr_90():
    with patch("app.services.billing_credits.cached_cbr_rub_per_usd_sync", return_value=90.0):
        assert credits_total_rub(500) == Decimal("450.00")


def test_purchase_bonus_15_percent():
    base = 5000
    granted = apply_purchase_bonus_credits(base, 4500)
    assert granted == 5750
