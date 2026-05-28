"""Каталог тарифов ModelMate: tier × billing_plan × период."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.billing_plan import BILLING_PLAN_BYOK, BILLING_PLAN_MANAGED, normalize_billing_plan
from app.services.referral import referral_public_dict

PlanTier = Literal["solo", "pro", "studio"]
BillingPeriod = Literal["month", "year"]
BillingPlanKind = Literal["managed", "byok"]

TIER_SOLO: PlanTier = "solo"
TIER_PRO: PlanTier = "pro"
TIER_STUDIO: PlanTier = "studio"
PERIOD_MONTH: BillingPeriod = "month"
PERIOD_YEAR: BillingPeriod = "year"

TIERS: tuple[PlanTier, ...] = (TIER_SOLO, TIER_PRO, TIER_STUDIO)
PERIODS: tuple[BillingPeriod, ...] = (PERIOD_MONTH, PERIOD_YEAR)

# Устаревшие product id → актуальный тариф
LEGACY_PRODUCT_MAP: dict[str, str] = {
    "sub_managed_month": "sub_managed_solo_month",
    "sub_byok_month": "sub_byok_solo_month",
}


@dataclass(frozen=True, slots=True)
class PlanLimits:
    max_users: int
    max_models: int
    max_dialogs_per_month: int | None
    max_grok_per_month: int | None


@dataclass(frozen=True, slots=True)
class PlanSpec:
    product: str
    billing_plan: BillingPlanKind
    tier: PlanTier
    period: BillingPeriod
    price_rub: int
    title_ru: str
    managed_monthly_credits: int
    limits: PlanLimits
    popular: bool = False


def _limits(tier: PlanTier) -> PlanLimits:
    if tier == TIER_SOLO:
        return PlanLimits(
            max_users=1,
            max_models=1,
            max_dialogs_per_month=1000,
            max_grok_per_month=500,
        )
    if tier == TIER_PRO:
        return PlanLimits(
            max_users=3,
            max_models=3,
            max_dialogs_per_month=5000,
            max_grok_per_month=2000,
        )
    return PlanLimits(
        max_users=10,
        max_models=10,
        max_dialogs_per_month=None,
        max_grok_per_month=10000,
    )


def _product(billing: BillingPlanKind, tier: PlanTier, period: BillingPeriod) -> str:
    return f"sub_{billing}_{tier}_{period}"


def managed_period_credits(spec: PlanSpec) -> int:
    """Кредиты, начисляемые при оплате периода: месяц — monthly, год — 12× monthly."""
    if spec.billing_plan != BILLING_PLAN_MANAGED or spec.managed_monthly_credits <= 0:
        return 0
    if spec.period == PERIOD_YEAR:
        return spec.managed_monthly_credits * 12
    return spec.managed_monthly_credits


def _build_specs() -> dict[str, PlanSpec]:
    prices_month_byok: dict[PlanTier, int] = {
        TIER_SOLO: 990,
        TIER_PRO: 2490,
        TIER_STUDIO: 5990,
    }
    prices_month_managed: dict[PlanTier, int] = {
        TIER_SOLO: 1990,
        TIER_PRO: 4990,
        TIER_STUDIO: 11990,
    }
    prices_year_byok: dict[PlanTier, int] = {
        TIER_SOLO: 8900,
        TIER_PRO: 22400,
        TIER_STUDIO: 53900,
    }
    prices_year_managed: dict[PlanTier, int] = {
        TIER_SOLO: 17900,
        TIER_PRO: 44900,
        TIER_STUDIO: 107900,
    }
    managed_credits: dict[PlanTier, int] = {
        TIER_SOLO: 150,
        TIER_PRO: 400,
        TIER_STUDIO: 1200,
    }
    titles: dict[tuple[BillingPlanKind, PlanTier], str] = {
        (BILLING_PLAN_BYOK, TIER_SOLO): "BYOK Solo",
        (BILLING_PLAN_BYOK, TIER_PRO): "BYOK Pro",
        (BILLING_PLAN_BYOK, TIER_STUDIO): "BYOK Studio",
        (BILLING_PLAN_MANAGED, TIER_SOLO): "Managed Solo",
        (BILLING_PLAN_MANAGED, TIER_PRO): "Managed Pro",
        (BILLING_PLAN_MANAGED, TIER_STUDIO): "Managed Studio",
    }
    out: dict[str, PlanSpec] = {}
    for billing in (BILLING_PLAN_BYOK, BILLING_PLAN_MANAGED):
        month_prices = prices_month_byok if billing == BILLING_PLAN_BYOK else prices_month_managed
        year_prices = prices_year_byok if billing == BILLING_PLAN_BYOK else prices_year_managed
        for tier in TIERS:
            for period, price_map in ((PERIOD_MONTH, month_prices), (PERIOD_YEAR, year_prices)):
                prod = _product(billing, tier, period)
                out[prod] = PlanSpec(
                    product=prod,
                    billing_plan=billing,
                    tier=tier,
                    period=period,
                    price_rub=price_map[tier],
                    title_ru=titles[(billing, tier)],
                    managed_monthly_credits=managed_credits[tier] if billing == BILLING_PLAN_MANAGED else 0,
                    limits=_limits(tier),
                    popular=(tier == TIER_PRO),
                )
    return out


PLAN_SPECS: dict[str, PlanSpec] = _build_specs()


def normalize_plan_tier(raw: str | None) -> PlanTier:
    s = (raw or TIER_SOLO).strip().lower()
    if s in TIERS:
        return s  # type: ignore[return-value]
    return TIER_SOLO


def resolve_product_id(product: str) -> str:
    p = (product or "").strip()
    return LEGACY_PRODUCT_MAP.get(p, p)


def get_plan_spec(product: str) -> PlanSpec | None:
    return PLAN_SPECS.get(resolve_product_id(product))


def list_subscription_products() -> list[PlanSpec]:
    return sorted(PLAN_SPECS.values(), key=lambda s: (s.billing_plan, TIERS.index(s.tier), s.period))


def tier_label_ru(tier: PlanTier) -> str:
    return {"solo": "Solo", "pro": "Pro", "studio": "Studio"}[tier]


def plan_display_name(billing_plan: str | None, plan_tier: str | None) -> str:
    bp = normalize_billing_plan(billing_plan)
    tier = normalize_plan_tier(plan_tier)
    mode = "BYOK" if bp == BILLING_PLAN_BYOK else "Managed"
    return f"{mode} {tier_label_ru(tier)}"


def catalog_public_dict() -> dict:
    """Сериализация для /api/health и маркетинга."""
    plans = []
    for spec in list_subscription_products():
        lim = spec.limits
        plans.append(
            {
                "product": spec.product,
                "billing_plan": spec.billing_plan,
                "tier": spec.tier,
                "period": spec.period,
                "price_rub": spec.price_rub,
                "title": spec.title_ru,
                "popular": spec.popular,
                "managed_monthly_credits": spec.managed_monthly_credits,
                "managed_period_credits": managed_period_credits(spec),
                "limits": {
                    "max_users": lim.max_users,
                    "max_models": lim.max_models,
                    "max_dialogs_per_month": lim.max_dialogs_per_month,
                    "max_grok_per_month": lim.max_grok_per_month,
                },
            }
        )
    return {
        "plans": plans,
        "legacy_products": LEGACY_PRODUCT_MAP,
        "wavespeed_referral_url": "https://wavespeed.ai/?ref=modelmate",
        "referral": referral_public_dict(),
    }
