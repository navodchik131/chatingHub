"""Агрегаты админ-панели: вспомогательные функции."""

from __future__ import annotations

from app.services.admin_analytics import _pct, _usage_event_revenue_rub
from app.services.admin_segments import SEGMENT_TITLES, VALID_ADMIN_SEGMENTS


def test_pct_rounds() -> None:
    assert _pct(3, 10) == 30.0
    assert _pct(1, 3) == 33.3


def test_pct_zero_total() -> None:
    assert _pct(5, 0) == 0.0


def test_valid_segments_match_titles() -> None:
    assert VALID_ADMIN_SEGMENTS == frozenset(SEGMENT_TITLES.keys())
    assert "yookassa_payments" in VALID_ADMIN_SEGMENTS
    assert "zombie" in VALID_ADMIN_SEGMENTS


def test_usage_event_revenue_subscription_bonus_by_gateway() -> None:
    meta = {
        "payment_ref": "pay-1",
        "payment_kind": "yookassa",
        "product": "sub_standard_solo_month",
    }
    assert _usage_event_revenue_rub("standard_subscription_bonus", meta) == 1990

    meta["payment_kind"] = "tribute"
    assert _usage_event_revenue_rub("standard_subscription_bonus", meta) == 1990

    meta["payment_kind"] = "credits"
    assert _usage_event_revenue_rub("standard_subscription_bonus", meta) == 0


def test_usage_event_revenue_pro_subscription_counted() -> None:
    """Pro-подписка не даёт бонусных кредитов, но выручку приносит."""
    meta = {
        "payment_ref": "pay-pro-1",
        "payment_kind": "yookassa",
        "product": "sub_pro_solo_month",
        "amount_rub": 990,
    }
    assert _usage_event_revenue_rub("subscription_payment", meta) == 990


def test_usage_event_revenue_uses_actual_amount_paid() -> None:
    """При партнёрской скидке считаем уплаченное, а не цену каталога."""
    meta = {
        "payment_ref": "pay-2",
        "payment_kind": "yookassa",
        "product": "sub_standard_solo_month",
        "amount_rub": 1492,
    }
    assert _usage_event_revenue_rub("subscription_payment", meta) == 1492

    # Без суммы в meta — фолбэк на каталог.
    del meta["amount_rub"]
    assert _usage_event_revenue_rub("subscription_payment", meta) == 1990


def test_usage_event_revenue_subscription_paid_with_credits_is_not_revenue() -> None:
    meta = {
        "payment_ref": "credits:1:sub_pro_solo_month",
        "payment_kind": "credits",
        "product": "sub_pro_solo_month",
        "amount_rub": 990,
    }
    assert _usage_event_revenue_rub("subscription_payment", meta) == 0


def test_usage_event_revenue_legacy_managed_bonus_counted() -> None:
    """Оплаты до переименования Managed→Standard тоже должны считаться."""
    meta = {
        "payment_ref": "pay-old",
        "payment_kind": "yookassa",
        "product": "sub_standard_solo_month",
    }
    assert _usage_event_revenue_rub("managed_subscription_bonus", meta) == 1990


def test_segment_titles_non_empty() -> None:
    from app.services.admin_segments import SEGMENT_TITLES

    for key, title in SEGMENT_TITLES.items():
        assert key
        assert title.strip()
