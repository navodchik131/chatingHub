from __future__ import annotations

from app.db.models import LlmConnection, WavespeedConnection

BILLING_PLAN_MANAGED = "managed"
BILLING_PLAN_BYOK = "byok"


def normalize_billing_plan(raw: str | None) -> str:
    s = (raw or BILLING_PLAN_MANAGED).strip().lower()
    return BILLING_PLAN_BYOK if s == BILLING_PLAN_BYOK else BILLING_PLAN_MANAGED


def platform_covers_studio_api_costs(plan: str) -> bool:
    """True — списываем кредиты (расходует платформа или гибрид с нашими ключами)."""
    return normalize_billing_plan(plan) == BILLING_PLAN_MANAGED


def byok_keys_ready_for_llm(*, plan: str, llm: LlmConnection | None) -> bool:
    if platform_covers_studio_api_costs(plan):
        return True
    return bool(llm and (llm.api_key_encrypted or "").strip())


def byok_keys_ready_for_wavespeed(*, plan: str, ws: WavespeedConnection | None) -> bool:
    if platform_covers_studio_api_costs(plan):
        return True
    return bool(ws and (ws.api_key_encrypted or "").strip())


def assert_byok_llm(plan: str, llm: LlmConnection | None) -> None:
    from fastapi import HTTPException

    if platform_covers_studio_api_costs(plan):
        return
    if not byok_keys_ready_for_llm(plan=plan, llm=llm):
        raise HTTPException(
            status_code=400,
            detail="Тариф BYOK: сохраните API-ключ LLM (OpenAI-совместимый, напр. Grok) в разделе интеграций.",
        )


def assert_byok_wavespeed(plan: str, ws: WavespeedConnection | None) -> None:
    from fastapi import HTTPException

    if platform_covers_studio_api_costs(plan):
        return
    if not byok_keys_ready_for_wavespeed(plan=plan, ws=ws):
        raise HTTPException(
            status_code=400,
            detail="Тариф BYOK: сохраните ключ WaveSpeed в интеграциях.",
        )
