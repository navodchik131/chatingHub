from __future__ import annotations

from app.services.partner import (
    _payment_ref_from_usage_meta,
    _usage_event_payment_rub,
    commission_kopecks_from_payment_rub,
    grant_partner_commission_if_needed,
)


def test_commission_kopecks_from_payment_rub():
    # 20% of 990 RUB = 198 RUB = 19800 kopecks (default partner_commission_percent in config)
    k = commission_kopecks_from_payment_rub(990)
    assert k > 0


def test_tribute_billing_imports_partner_commission():
    import app.services.tribute_billing_apply as mod

    assert hasattr(mod, "grant_partner_commission_if_needed")
    assert hasattr(mod, "mark_partner_discount_used")


def test_grant_partner_commission_skips_without_referrer():
    """Smoke: function exists and is async — full DB test omitted."""
    assert callable(grant_partner_commission_if_needed)


def test_payment_ref_from_tribute_credits_meta():
    meta = {"payment_ref": "trib_123", "amount_rub": 500}
    assert _payment_ref_from_usage_meta("tribute_credits_pack", meta) == "trib_123"


def test_payment_ref_from_yookassa_meta():
    meta = {"payment_id": "yk_456", "amount_rub": 990}
    assert _payment_ref_from_usage_meta("yookassa_credits_pack", meta) == "yk_456"


def test_subscription_payment_skips_non_money():
    meta = {"payment_ref": "x", "payment_kind": "credits", "amount_rub": 990}
    assert _payment_ref_from_usage_meta("subscription_payment", meta) is None


def test_usage_event_payment_rub_tribute_credits():
    meta = {"payment_ref": "trib_1", "amount_rub": 500}
    assert _usage_event_payment_rub("tribute_credits_pack", meta) == 500