"""Расчёт суммы покупки кредитов для ЮKassa и оплаты подписки кредитами."""
from __future__ import annotations

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, ROUND_UP

from app.config import settings


def credit_unit_price_rub() -> Decimal:
    return Decimal(settings.billing_credits_unit_price_rub)


def rub_to_credits_ceil(amount_rub: int | Decimal) -> int:
    """Сколько кредитов списать за сумму в рублях (подписка, пересчёт рефералки)."""
    unit = credit_unit_price_rub()
    if unit <= 0:
        raise ValueError("credit unit price must be positive")
    amt = Decimal(amount_rub)
    return int((amt / unit).to_integral_value(rounding=ROUND_UP))


def credits_to_rub_value(credits: int) -> Decimal:
    return (Decimal(max(0, credits)) * credit_unit_price_rub()).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def referrer_reward_credits_from_payment_rub(amount_rub: Decimal) -> int:
    """10% (или referral_referrer_payment_percent) от оплаты → кредиты рефереру."""
    pct = Decimal(int(settings.referral_referrer_payment_percent)) / Decimal(100)
    unit = credit_unit_price_rub()
    if unit <= 0 or amount_rub <= 0 or pct <= 0:
        return 0
    reward_rub = (amount_rub * pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int((reward_rub / unit).to_integral_value(rounding=ROUND_DOWN))


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
