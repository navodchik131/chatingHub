from decimal import Decimal
from unittest.mock import patch

from app.config import settings
from app.services.billing_credits import (
    apply_purchase_bonus_credits,
    credits_total_rub,
    purchase_rub_per_usd,
    referrer_reward_credits_from_payment_rub,
    rub_to_credits_ceil,
    standard_subscription_monthly_credits,
)


def test_purchase_rub_per_usd_uses_floor_when_cbr_lower():
    with patch("app.services.billing_credits.cached_cbr_rub_per_usd_sync", return_value=90.0):
        with patch.object(settings, "billing_credits_rub_per_usd_floor", 97.0):
            assert purchase_rub_per_usd() == 97.0


def test_purchase_rub_per_usd_follows_cbr_when_above_floor():
    with patch("app.services.billing_credits.cached_cbr_rub_per_usd_sync", return_value=102.0):
        with patch.object(settings, "billing_credits_rub_per_usd_floor", 97.0):
            assert purchase_rub_per_usd() == 102.0


def test_rub_to_credits_ceil_at_floor_97():
    with patch("app.services.billing_credits.cached_cbr_rub_per_usd_sync", return_value=90.0):
        with patch.object(settings, "billing_credits_rub_per_usd_floor", 97.0):
            # 990 ₽ / 97 × 100 → ceil 1020.618… → 1021
            assert rub_to_credits_ceil(990) == 1021


def test_referrer_ten_percent_990_at_floor_97():
    with patch("app.services.billing_credits.cached_cbr_rub_per_usd_sync", return_value=90.0):
        with patch.object(settings, "billing_credits_rub_per_usd_floor", 97.0):
            # 10% = 99 ₽ → ceil(99*100/97) = 103
            assert referrer_reward_credits_from_payment_rub(Decimal("990")) == 103


def test_credits_total_rub_500_at_floor_97():
    with patch("app.services.billing_credits.cached_cbr_rub_per_usd_sync", return_value=90.0):
        with patch.object(settings, "billing_credits_rub_per_usd_floor", 97.0):
            assert credits_total_rub(500) == Decimal("485.00")


def test_purchase_bonus_15_percent():
    base = 5000
    granted = apply_purchase_bonus_credits(base, 4500)
    assert granted == 5750


def test_standard_subscription_monthly_credits_about_half_at_floor_97():
    with patch("app.services.billing_credits.cached_cbr_rub_per_usd_sync", return_value=90.0):
        with patch.object(settings, "billing_credits_rub_per_usd_floor", 97.0):
            # half of 1990 = 995 → ceil 1026 → round down to 50 = 1000
            assert standard_subscription_monthly_credits(1990) == 1000
            # half of 4990 = 2495 → ceil 2573 → 2550
            assert standard_subscription_monthly_credits(4990) == 2550
            # half of 11990 = 5995 → ceil 6181 → 6150
            assert standard_subscription_monthly_credits(11990) == 6150
