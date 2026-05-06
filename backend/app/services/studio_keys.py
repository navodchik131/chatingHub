from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import LlmConnection, Subscription, WavespeedConnection
from app.services.billing_plan import (
    BILLING_PLAN_BYOK,
    assert_byok_llm,
    assert_byok_wavespeed,
    normalize_billing_plan,
    platform_covers_studio_api_costs,
)
from app.services.crypto_secret import decrypt_secret
from app.services.studio_openai import StudioOpenAiCredentials


async def load_owner_studio_billing(
    session: AsyncSession, owner_id: int
) -> tuple[Subscription | None, LlmConnection | None, WavespeedConnection | None, str]:
    sub = await session.scalar(select(Subscription).where(Subscription.user_id == owner_id))
    llm = await session.scalar(select(LlmConnection).where(LlmConnection.user_id == owner_id))
    ws = await session.scalar(
        select(WavespeedConnection).where(WavespeedConnection.user_id == owner_id)
    )
    plan = normalize_billing_plan(sub.billing_plan if sub else None)
    return sub, llm, ws, plan


def studio_llm_credentials(*, plan: str, llm_row: LlmConnection | None) -> StudioOpenAiCredentials:
    if platform_covers_studio_api_costs(plan):
        key = (settings.openai_api_key or "").strip()
        if not key:
            raise HTTPException(
                status_code=503,
                detail="На сервере не задан OPENAI_API_KEY для тарифа «всё включено».",
            )
        base = (settings.openai_base_url or "").strip().rstrip("/") or "https://api.openai.com/v1"
        org = (settings.openai_organization or "").strip()
        return StudioOpenAiCredentials(api_key=key, base_url=base, organization=org)
    assert_byok_llm(plan, llm_row)
    try:
        key = decrypt_secret(llm_row.api_key_encrypted)  # type: ignore[union-attr]
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Не удалось расшифровать ключ LLM") from e
    raw_base = (llm_row.base_url or "").strip() if llm_row else ""  # type: ignore[union-attr]
    base = raw_base.rstrip("/") if raw_base else (settings.openai_base_url or "").strip().rstrip("/")
    if not base:
        base = "https://api.openai.com/v1"
    return StudioOpenAiCredentials(api_key=key, base_url=base, organization="")


def studio_wavespeed_api_key(*, plan: str, ws_row: WavespeedConnection | None) -> str:
    if platform_covers_studio_api_costs(plan):
        plat = (settings.wavespeed_platform_api_key or "").strip()
        if plat:
            return plat
        if ws_row and (ws_row.api_key_encrypted or "").strip():
            try:
                return decrypt_secret(ws_row.api_key_encrypted)
            except ValueError:
                pass
        raise HTTPException(
            status_code=503,
            detail="Для тарифа «всё включено» задайте WAVESPEED_PLATFORM_API_KEY на сервере "
            "или сохраните WaveSpeed в интеграциях (временный fallback).",
        )
    assert_byok_wavespeed(plan, ws_row)
    try:
        return decrypt_secret(ws_row.api_key_encrypted)  # type: ignore[union-attr]
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail="Не удалось расшифровать ключ WaveSpeed"
        ) from e


def studio_charges_credits(plan: str) -> bool:
    """True — операции студии расходуют кредиты (тариф managed)."""
    return platform_covers_studio_api_costs(plan)


def apply_studio_credit_cost(plan: str, base_cost: int) -> int:
    if studio_charges_credits(plan):
        return max(0, base_cost)
    return 0
