"""Бесплатные демо-генерации картинок (счётчик)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import CreditAccount, UsageEvent, User
from app.services.billing_plan import is_credits_plan, normalize_billing_plan, studio_charges_credits
from app.services.credits import ensure_can_consume_credits, record_usage
from app.services.studio_image_pricing import (
    demo_allowed_models_label,
    demo_request_eligible_for_free_slot as pricing_demo_eligible,
    quote_studio_image_credits,
)
from app.services.studio_keys import apply_studio_credit_cost

DEMO_USAGE_KIND = "demo_studio_image"

DEMO_ELIGIBLE_USAGE_KINDS = frozenset(
    {
        "studio_prompt_refine",
        "studio_inpaint",
    }
)

_OWNER_PAYMENT_USAGE_KINDS = frozenset(
    {
        "yookassa_credits_pack",
        "managed_subscription_bonus",
        "standard_subscription_bonus",
        "subscription_credits_payment",
    }
)


def demo_generations_grant() -> int:
    return max(0, int(settings.demo_generations_grant))


def demo_request_eligible_for_free_slot(
    *,
    wave_model_id: str | None,
    grok_pipeline: str,
    wave_profile: str | None = "nsfw",
    wan_edit_tier: str | None = "standard",
) -> bool:
    return pricing_demo_eligible(
        wave_model_id=wave_model_id,
        grok_pipeline=grok_pipeline,
        wave_profile=wave_profile,
        wan_edit_tier=wan_edit_tier,
    )


def assert_demo_only_user_model_allowed(
    *,
    plan: str,
    demo_remaining: int,
    credits_balance: int,
    wave_model_id: str | None,
    grok_pipeline: str,
    wave_profile: str | None = "nsfw",
    wan_edit_tier: str | None = "standard",
) -> None:
    """Credits без баланса: только демо-модели; иначе — пополнить кредиты."""
    if not is_credits_plan(plan) or demo_remaining <= 0 or credits_balance > 0:
        return
    if demo_request_eligible_for_free_slot(
        wave_model_id=wave_model_id,
        grok_pipeline=grok_pipeline,
        wave_profile=wave_profile,
        wan_edit_tier=wan_edit_tier,
    ):
        return
    raise HTTPException(
        status_code=402,
        detail=(
            f"Бесплатные генерации: {demo_allowed_models_label()}. "
            "Пополните кредиты для других моделей и режимов."
        ),
    )


async def prepare_studio_image_billing(
    session: AsyncSession,
    actor: User,
    billing: User,
    *,
    plan: str,
    base_cost: int,
    usage_kind: str,
    quoted_cost: int | None = None,
    wave_model_id: str | None = None,
    grok_pipeline: str = "standard",
    wave_profile: str | None = "nsfw",
    wan_edit_tier: str | None = "standard",
) -> tuple[User, int, bool]:
    """
    Демо-счётчик или кредиты. quoted_cost — из studio_image_pricing; иначе base_cost.
    """
    if not studio_charges_credits(plan):
        return billing, 0, False

    cost = apply_studio_credit_cost(plan, quoted_cost if quoted_cost is not None else base_cost)
    if cost <= 0:
        return billing, 0, False

    acc = billing.credit_account
    if acc is None:
        acc = await session.get(CreditAccount, billing.id)
    demo_rem = int(acc.demo_generations_remaining) if acc is not None else 0

    if (
        usage_kind in DEMO_ELIGIBLE_USAGE_KINDS
        and demo_rem > 0
        and is_credits_plan(plan)
        and demo_request_eligible_for_free_slot(
            wave_model_id=wave_model_id,
            grok_pipeline=grok_pipeline,
            wave_profile=wave_profile,
            wan_edit_tier=wan_edit_tier,
        )
    ):
        if acc is None:
            acc = CreditAccount(
                user_id=billing.id,
                balance=0,
                demo_generations_remaining=demo_rem,
            )
            session.add(acc)
            await session.flush()
        acc.demo_generations_remaining = max(0, demo_rem - 1)
        await session.flush()
        return billing, 0, True

    billing = await ensure_can_consume_credits(session, actor, cost)
    return billing, cost, False


async def record_studio_image_billing(
    session: AsyncSession,
    actor: User,
    billing: User,
    *,
    usage_kind: str,
    cost: int,
    used_demo: bool,
    meta: dict[str, Any] | None = None,
) -> None:
    meta_full = dict(meta or {})
    if used_demo:
        if actor.id != billing.id:
            meta_full["actor_user_id"] = actor.id
        meta_full["demo"] = True
        session.add(
            UsageEvent(
                user_id=billing.id,
                kind=DEMO_USAGE_KIND,
                credits_delta=0,
                meta=json.dumps(meta_full, ensure_ascii=False),
            )
        )
        await session.flush()
        return
    if cost > 0:
        await record_usage(session, actor, billing, usage_kind, cost, meta=meta_full)


def raise_studio_access_denied(*, demo_remaining: int, credits: int) -> None:
    if demo_remaining > 0 or credits > 0:
        return
    raise HTTPException(
        status_code=402,
        detail=(
            "Бесплатные генерации закончились. Пополните кредиты или оформите подписку "
            "Standard / Pro в разделе «Тариф и баланс»."
        ),
    )


def resolve_image_credit_cost(
    plan: str,
    *,
    wave_model_id: str | None = None,
    wan_edit_tier: str | None = None,
    grok_pipeline: str = "standard",
    extra_reference_count: int = 0,
    legacy_base: int | None = None,
) -> int:
    """Кредиты с учётом модели; fallback на legacy_base если pricing не задан."""
    from app.services.studio_image_pricing import GrokPipelineKind

    gp: GrokPipelineKind = "standard"
    if grok_pipeline in ("none", "light", "standard", "heavy", "workflow"):
        gp = grok_pipeline  # type: ignore[assignment]
    quoted = quote_studio_image_credits(
        wave_model_id=wave_model_id,
        wan_edit_tier=wan_edit_tier,
        grok_pipeline=gp,
        extra_reference_count=extra_reference_count,
    )
    if legacy_base is not None and quoted <= 0:
        quoted = legacy_base
    return apply_studio_credit_cost(plan, quoted)
