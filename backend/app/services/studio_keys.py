from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import CreditAccount, LlmConnection, Subscription, SubscriptionStatus, WavespeedConnection
from app.services.billing_plan import (
    assert_pro_wavespeed,
    is_credits_plan,
    is_pro_plan,
    normalize_billing_plan,
    platform_covers_studio_api_costs,
)
from app.services.crypto_secret import decrypt_secret
from app.services.entitlements import subscription_is_paid_active
from app.services.studio_openai import StudioOpenAiCredentials


def demo_uses_platform_wavespeed(
    *,
    demo_generations_remaining: int,
    billing_plan: str,
    owner_subscription: Subscription | None,
) -> bool:
    if demo_generations_remaining <= 0:
        return False
    if not is_credits_plan(billing_plan):
        return False
    if owner_subscription and subscription_is_paid_active(owner_subscription):
        return False
    return bool((settings.wavespeed_platform_api_key or "").strip())


async def load_owner_studio_billing(
    session: AsyncSession, owner_id: int
) -> tuple[Subscription | None, LlmConnection | None, WavespeedConnection | None, str, int, int]:
    sub = await session.scalar(select(Subscription).where(Subscription.user_id == owner_id))
    llm = await session.scalar(select(LlmConnection).where(LlmConnection.user_id == owner_id))
    ws = await session.scalar(
        select(WavespeedConnection).where(WavespeedConnection.user_id == owner_id)
    )
    cr = await session.scalar(select(CreditAccount).where(CreditAccount.user_id == owner_id))
    plan = normalize_billing_plan(sub.billing_plan if sub else None)
    bal = int(cr.balance) if cr is not None else 0
    demo_rem = int(cr.demo_generations_remaining) if cr is not None else 0
    return sub, llm, ws, plan, bal, demo_rem


def studio_llm_credentials(*, plan: str | None = None, llm_row: LlmConnection | None = None) -> StudioOpenAiCredentials:
    _ = plan, llm_row
    key = (settings.openai_api_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Студия временно недоступна. Обратитесь к администратору.",
        )
    base = (settings.openai_base_url or "").strip().rstrip("/") or "https://api.openai.com/v1"
    org = (settings.openai_organization or "").strip()
    return StudioOpenAiCredentials(api_key=key, base_url=base, organization=org)


def studio_wavespeed_api_key(
    *,
    plan: str,
    ws_row: WavespeedConnection | None,
    owner_subscription: Subscription | None,
    demo_generations_remaining: int = 0,
) -> str:
    plan_n = normalize_billing_plan(plan)
    if demo_uses_platform_wavespeed(
        demo_generations_remaining=demo_generations_remaining,
        billing_plan=plan_n,
        owner_subscription=owner_subscription,
    ):
        key = (settings.wavespeed_platform_api_key or "").strip()
        if not key:
            raise HTTPException(
                status_code=503,
                detail="Демо-генерации временно недоступны. Попробуйте позже или пополните кредиты.",
            )
        return key

    if platform_covers_studio_api_costs(plan_n) and subscription_is_paid_active(owner_subscription):
        key = (settings.wavespeed_platform_api_key or "").strip()
        if not key:
            raise HTTPException(
                status_code=503,
                detail="Генерация временно недоступна. Обратитесь к администратору.",
            )
        return key

    if is_credits_plan(plan_n) and platform_covers_studio_api_costs(plan_n):
        key = (settings.wavespeed_platform_api_key or "").strip()
        if key:
            return key

    assert_pro_wavespeed(plan_n, ws_row)
    try:
        return decrypt_secret(ws_row.api_key_encrypted)  # type: ignore[union-attr]
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail="Не удалось расшифровать ключ WaveSpeed"
        ) from e


def studio_charges_credits(plan: str) -> bool:
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
    demo_generations_remaining: int = 0,
) -> tuple[bool, bool]:
    plan_n = normalize_billing_plan(plan)
    platform_ws_ok = bool((settings.wavespeed_platform_api_key or "").strip())
    user_ws_ok = bool(ws_row and (ws_row.api_key_encrypted or "").strip())

    if demo_uses_platform_wavespeed(
        demo_generations_remaining=demo_generations_remaining,
        billing_plan=plan_n,
        owner_subscription=sub,
    ):
        return platform_ws_ok, platform_ws_ok

    if platform_covers_studio_api_costs(plan_n) and subscription_is_paid_active(sub):
        return platform_ws_ok, platform_ws_ok

    if is_credits_plan(plan_n) and platform_ws_ok:
        return platform_ws_ok, True

    if is_pro_plan(plan_n):
        return user_ws_ok, False

    return user_ws_ok, False
