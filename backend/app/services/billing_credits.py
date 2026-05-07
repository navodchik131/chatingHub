"""Расчёт суммы покупки кредитов для ЮKassa и проверки вебхука."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.config import settings


def credits_unit_for_quantity(n: int) -> Decimal:
    if n >= settings.billing_credits_bulk_from:
        return settings.billing_credits_bulk_unit_price_rub
    return settings.billing_credits_unit_price_rub


def credits_total_rub(n: int) -> Decimal:
    unit = credits_unit_for_quantity(n)
    return (Decimal(n) * unit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def credits_amount_yookassa_value(n: int) -> str:
    return f"{credits_total_rub(n):.2f}"


def assert_credits_quantity_allowed(n: int) -> None:
    if n < settings.billing_credits_min_purchase:
        msg = f"Минимум {settings.billing_credits_min_purchase} кредитов"
        raise ValueError(msg)
    if n > settings.billing_credits_max_purchase:
        msg = f"Максимум {settings.billing_credits_max_purchase} кредитов за раз"
        raise ValueError(msg)


def legacy_pack_total_rub() -> Decimal:
    return Decimal(int(settings.billing_credit_pack_price_rub)).quantize(Decimal("0.01"))
