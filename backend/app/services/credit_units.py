"""1 credit = 1 USD cent (0.01 USD)."""

from __future__ import annotations

import math

from app.config import settings

CREDITS_PER_USD = 100


def usd_to_credits(usd: float, *, markup_usd: float | None = None) -> int:
    """API cost in USD → integer credits (cent-units), minimum 1."""
    mark = (
        float(settings.studio_operation_markup_usd)
        if markup_usd is None
        else float(markup_usd)
    )
    total = max(0.0, float(usd) + mark)
    return max(1, int(math.ceil(total * CREDITS_PER_USD)))


def credits_to_usd(credits: int) -> float:
    return max(0, int(credits)) / CREDITS_PER_USD


def rub_per_credit_from_cbr(cbr_rub_per_usd: float) -> float:
    """₽ за 1 cent-credit."""
    if cbr_rub_per_usd <= 0:
        return 0.0
    return float(cbr_rub_per_usd) / CREDITS_PER_USD


def legacy_to_cent_credits(
    old_balance: int,
    *,
    old_rub_per_credit: float,
    cbr_rub_per_usd: float,
) -> int:
    """Convert pre-v2 integer balance preserving paid RUB value."""
    if old_balance <= 0:
        return 0
    if cbr_rub_per_usd <= 0 or old_rub_per_credit <= 0:
        return max(0, int(old_balance))
    factor = float(old_rub_per_credit) * CREDITS_PER_USD / float(cbr_rub_per_usd)
    return max(0, int(round(old_balance * factor)))


def credit_units_public() -> dict[str, float | int | str]:
    from app.services.fx_rate import cached_cbr_rub_per_usd_sync

    cbr = cached_cbr_rub_per_usd_sync()
    rub_per_credit = cbr / CREDITS_PER_USD
    return {
        "model": "usd_cent",
        "credits_per_usd": CREDITS_PER_USD,
        "usd_per_credit": 0.01,
        "rub_per_credit": round(rub_per_credit, 4),
        "rub_per_usd_cbr": round(cbr, 4),
        "operation_markup_usd": float(settings.studio_operation_markup_usd),
    }
