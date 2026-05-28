from decimal import Decimal

from app.config import settings
from app.services.billing_credits import (
    referrer_reward_credits_from_payment_rub,
    rub_to_credits_ceil,
)


def test_rub_to_credits_ceil_990_at_37(monkeypatch):
    monkeypatch.setattr(settings, "billing_credits_unit_price_rub", Decimal("3.7"))
    assert rub_to_credits_ceil(990) == 268


def test_referrer_ten_percent_990(monkeypatch):
    monkeypatch.setattr(settings, "billing_credits_unit_price_rub", Decimal("3.7"))
    monkeypatch.setattr(settings, "referral_referrer_payment_percent", 10)
    assert referrer_reward_credits_from_payment_rub(Decimal("990")) == 26
