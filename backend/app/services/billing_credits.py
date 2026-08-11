"""Расчёт суммы покупки кредитов для ЮKassa и оплаты подписки кредитами.

1 credit = 1 USD cent. Покупка: credits × CBR/100 ₽.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, ROUND_UP

from app.config import settings
from app.services.credit_units import CREDITS_PER_USD, credits_to_usd, rub_per_credit_from_cbr
from app.services.fx_rate import cached_cbr_rub_per_usd_sync


def rub_per_credit_purchase() -> Decimal:
    """₽ за 1 cent-credit по курсу ЦБ."""
    return Decimal(str(rub_per_credit_from_cbr(cached_cbr_rub_per_usd_sync())))


def credit_unit_price_rub() -> Decimal:
    """Обратная совместимость API / health."""
    return rub_per_credit_purchase()


def rub_to_credits_ceil(amount_rub: int | Decimal) -> int:
    """Сколько кредитов списать за сумму в рублях (подписка, пересчёт рефералки)."""
    cbr = Decimal(cached_cbr_rub_per_usd_sync())
    if cbr <= 0:
        raise ValueError("invalid CBR rate")
    amt = Decimal(amount_rub)
    return int((amt * Decimal(CREDITS_PER_USD) / cbr).to_integral_value(rounding=ROUND_UP))


def credits_to_rub_value(credits: int) -> Decimal:
    return (Decimal(max(0, credits)) * rub_per_credit_purchase()).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def referrer_reward_credits_from_payment_rub(amount_rub: Decimal) -> int:
    """10% (или referral_referrer_payment_percent) от оплаты → cent-credits."""
    pct = Decimal(int(settings.referral_referrer_payment_percent)) / Decimal(100)
    if amount_rub <= 0 or pct <= 0:
        return 0
    reward_rub = (amount_rub * pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return rub_to_credits_ceil(reward_rub)


def purchase_bonus_percent_for_rub(amount_rub: int) -> int:
    rub = int(amount_rub)
    if rub >= int(settings.billing_credits_bonus_from_rub_15pct):
        return 15
    if rub >= int(settings.billing_credits_bonus_from_rub_10pct):
        return 10
    if rub >= int(settings.billing_credits_bonus_from_rub_5pct):
        return 5
    return 0


def apply_purchase_bonus_credits(base_credits: int, amount_rub: int) -> int:
    pct = purchase_bonus_percent_for_rub(amount_rub)
    if pct <= 0:
        return max(0, int(base_credits))
    bonus = int(max(0, int(base_credits)) * pct / 100)
    return max(0, int(base_credits)) + bonus


def credits_unit_for_quantity(n: int) -> Decimal:
    """Единая цена покупки (bulk скидка через бонусные кредиты, не через ₽/кр.)."""
    _ = n
    return rub_per_credit_purchase()


def credits_total_rub(n: int) -> Decimal:
    """Стоимость n cent-credits в ₽."""
    return (Decimal(n) * rub_per_credit_purchase()).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def credits_amount_yookassa_value(n: int) -> str:
    return f"{credits_total_rub(n):.2f}"


def assert_credits_quantity_allowed(n: int) -> None:
    if n < settings.billing_credits_min_purchase:
        msg = f"Минимум {settings.billing_credits_min_purchase} кредитов (≈ ${credits_to_usd(settings.billing_credits_min_purchase):.2f})"
        raise ValueError(msg)
    if n > settings.billing_credits_max_purchase:
        msg = f"Максимум {settings.billing_credits_max_purchase} кредитов за раз"
        raise ValueError(msg)


def legacy_pack_total_rub() -> Decimal:
    return Decimal(int(settings.billing_credit_pack_price_rub)).quantize(Decimal("0.01"))


def billing_credits_pricing_public() -> dict:
    cbr = cached_cbr_rub_per_usd_sync()
    unit = float(rub_per_credit_purchase())
    return {
        "model": "usd_cent",
        "credits_per_usd": CREDITS_PER_USD,
        "usd_per_credit": 0.01,
        "rub_per_usd_cbr": round(cbr, 4),
        "unit_price_rub": unit,
        "bulk_unit_price_rub": unit,
        "min_quantity": int(settings.billing_credits_min_purchase),
        "bulk_from": int(settings.billing_credits_bulk_from),
        "bonus_from_rub_5pct": int(settings.billing_credits_bonus_from_rub_5pct),
        "bonus_from_rub_10pct": int(settings.billing_credits_bonus_from_rub_10pct),
        "bonus_from_rub_15pct": int(settings.billing_credits_bonus_from_rub_15pct),
        "pack_presets": [
            {"credits": 500, "rub": int(credits_total_rub(500)), "usd": 5.0},
            {"credits": 1110, "rub": int(credits_total_rub(1110)), "usd": 11.1},
            {"credits": 2500, "rub": int(credits_total_rub(2500)), "usd": 25.0},
            {"credits": 5000, "rub": int(credits_total_rub(5000)), "usd": 50.0},
        ],
    }
