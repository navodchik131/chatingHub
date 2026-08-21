from __future__ import annotations

from typing import TYPE_CHECKING

from app.db.models import LlmConnection, WavespeedConnection

if TYPE_CHECKING:
    from app.db.models import Subscription

BILLING_PLAN_CREDITS = "credits"
BILLING_PLAN_STANDARD = "standard"
BILLING_PLAN_PRO = "pro"

# Устаревшие значения в БД / API
BILLING_PLAN_MANAGED = BILLING_PLAN_STANDARD
BILLING_PLAN_BYOK = BILLING_PLAN_PRO

_LEGACY_PLAN_ALIASES = {
    "managed": BILLING_PLAN_STANDARD,
    "byok": BILLING_PLAN_PRO,
}


def normalize_billing_plan(raw: str | None) -> str:
    s = (raw or BILLING_PLAN_STANDARD).strip().lower()
    if s in _LEGACY_PLAN_ALIASES:
        return _LEGACY_PLAN_ALIASES[s]
    if s in (BILLING_PLAN_CREDITS, BILLING_PLAN_STANDARD, BILLING_PLAN_PRO):
        return s
    return BILLING_PLAN_STANDARD


def is_credits_plan(plan: str) -> bool:
    return normalize_billing_plan(plan) == BILLING_PLAN_CREDITS


def is_pro_plan(plan: str) -> bool:
    return normalize_billing_plan(plan) == BILLING_PLAN_PRO


def is_standard_plan(plan: str) -> bool:
    return normalize_billing_plan(plan) == BILLING_PLAN_STANDARD


def platform_covers_studio_api_costs(plan: str) -> bool:
    """Credits и Standard — платформенный/гибридный WS и списание кредитов."""
    p = normalize_billing_plan(plan)
    return p in (BILLING_PLAN_CREDITS, BILLING_PLAN_STANDARD)


def can_purchase_credits_pack(plan: str, sub: Subscription | None) -> bool:
    """Покупка кредитов — только при активной оплаченной подписке (любой тариф)."""
    from app.services.entitlements import subscription_is_paid_active

    _ = plan
    return subscription_is_paid_active(sub)


def studio_charges_credits(plan: str) -> bool:
    """Pro — генерации оплачиваются у WaveSpeed, кредиты студии не списываем."""
    return platform_covers_studio_api_costs(plan)


def plan_allows_chat(plan: str) -> bool:
    """Диалоги — на Standard / Pro (не на Credits)."""
    return not is_credits_plan(plan)


def plan_allows_companion(plan: str, tier: str | None = None) -> bool:
    """AI-бот (companion) — только Standard Studio и Pro Studio."""
    from app.services.plan_catalog import TIER_STUDIO, normalize_plan_tier

    if not plan_allows_chat(plan):
        return False
    if tier is None:
        return False
    return normalize_plan_tier(tier) == TIER_STUDIO


def byok_keys_ready_for_wavespeed(*, plan: str, ws: WavespeedConnection | None) -> bool:
    _ = plan
    return bool(ws and (ws.api_key_encrypted or "").strip())


def assert_pro_wavespeed(plan: str, ws: WavespeedConnection | None) -> None:
    from fastapi import HTTPException

    if platform_covers_studio_api_costs(plan):
        return
    if not byok_keys_ready_for_wavespeed(plan=plan, ws=ws):
        raise HTTPException(
            status_code=400,
            detail="Подключите API-ключ WaveSpeed в разделе «Интеграции».",
        )


# Совместимость со старым именем
assert_byok_wavespeed = assert_pro_wavespeed


def byok_keys_ready_for_llm(*, plan: str, llm: LlmConnection | None) -> bool:
    _ = plan, llm
    return True


def assert_byok_llm(plan: str, llm: LlmConnection | None) -> None:
    _ = plan, llm
