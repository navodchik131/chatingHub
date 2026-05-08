from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import CreditAccount, LlmConnection, Subscription, SubscriptionStatus, WavespeedConnection
from app.services.billing_plan import (
    assert_byok_wavespeed,
    normalize_billing_plan,
    platform_covers_studio_api_costs,
)
from app.services.crypto_secret import decrypt_secret
from app.services.entitlements import subscription_is_paid_active
from app.services.studio_openai import StudioOpenAiCredentials


async def load_owner_studio_billing(
    session: AsyncSession, owner_id: int
) -> tuple[Subscription | None, LlmConnection | None, WavespeedConnection | None, str, int]:
    sub = await session.scalar(select(Subscription).where(Subscription.user_id == owner_id))
    llm = await session.scalar(select(LlmConnection).where(LlmConnection.user_id == owner_id))
    ws = await session.scalar(
        select(WavespeedConnection).where(WavespeedConnection.user_id == owner_id)
    )
    cr = await session.scalar(select(CreditAccount).where(CreditAccount.user_id == owner_id))
    plan = normalize_billing_plan(sub.billing_plan if sub else None)
    bal = int(cr.balance) if cr is not None else 0
    return sub, llm, ws, plan, bal


def studio_llm_credentials(*, plan: str | None = None, llm_row: LlmConnection | None = None) -> StudioOpenAiCredentials:
    """Студия всегда использует LLM с сервера (OPENAI_* / xAI и т.д.); ключи из кабинета не применяются."""
    _ = plan, llm_row
    key = (settings.openai_api_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="На сервере не задан OPENAI_API_KEY для студии (текст и vision).",
        )
    base = (settings.openai_base_url or "").strip().rstrip("/") or "https://api.openai.com/v1"
    org = (settings.openai_organization or "").strip()
    return StudioOpenAiCredentials(api_key=key, base_url=base, organization=org)


def studio_wavespeed_api_key(
    *,
    plan: str,
    ws_row: WavespeedConnection | None,
    owner_subscription: Subscription | None,
) -> str:
    """
    WaveSpeed: период onboarding (trialing) — только ключ владельца из интеграций.
    Оплаченный Managed — платформенный ключ из .env.
    Оплаченный BYOK — ключ владельца.
    """
    st = owner_subscription.status if owner_subscription else None
    if st == SubscriptionStatus.trialing:
        assert_byok_wavespeed(plan, ws_row)
        try:
            return decrypt_secret(ws_row.api_key_encrypted)  # type: ignore[union-attr]
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail="Не удалось расшифровать ключ WaveSpeed"
            ) from e

    if platform_covers_studio_api_costs(plan) and subscription_is_paid_active(owner_subscription):
        key = (settings.wavespeed_platform_api_key or "").strip()
        if not key:
            raise HTTPException(
                status_code=503,
                detail="На сервере не задан WAVESPEED_PLATFORM_API_KEY для тарифа Managed (студия WaveSpeed).",
            )
        return key

    assert_byok_wavespeed(plan, ws_row)
    try:
        return decrypt_secret(ws_row.api_key_encrypted)  # type: ignore[union-attr]
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail="Не удалось расшифровать ключ WaveSpeed"
        ) from e


def studio_charges_credits(plan: str) -> bool:
    """True — операции студии расходуют кредиты (тариф managed, в т.ч. onboarding до оплаты)."""
    return platform_covers_studio_api_costs(plan)


def apply_studio_credit_cost(plan: str, base_cost: int) -> int:
    if studio_charges_credits(plan):
        return max(0, base_cost)
    return 0


def wavespeed_cabinet_flags(
    *,
    plan: str,
    ws_row: WavespeedConnection | None,
    sub: Subscription | None,
) -> tuple[bool, bool]:
    """
    (wavespeed_configured, wavespeed_managed_by_platform) — как в студии: пробный managed — только ключ из кабинета;
    оплаченный managed — WAVESPEED_PLATFORM_API_KEY; BYOK — ключ из кабинета.
    """
    platform_ws_ok = bool((settings.wavespeed_platform_api_key or "").strip())
    user_ws_ok = bool(ws_row and (ws_row.api_key_encrypted or "").strip())
    managed = platform_covers_studio_api_costs(plan)
    st = sub.status if sub else None
    if st == SubscriptionStatus.trialing:
        return user_ws_ok, False
    if managed and subscription_is_paid_active(sub):
        return platform_ws_ok, platform_ws_ok
    return user_ws_ok, False
