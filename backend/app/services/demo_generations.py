"""Бесплатные демо-генерации картинок (счётчик)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import CreditAccount, UsageEvent, User
from app.services.billing_plan import is_credits_plan, studio_charges_credits
from app.services.credits import ensure_can_consume_credits, record_usage
from app.services.device_signal import DeviceSignal
from app.services.studio_image_pricing import (
    demo_allowed_models_label,
    demo_request_eligible_for_free_slot as pricing_demo_eligible,
    quote_studio_image_credits,
)
from app.services.studio_keys import apply_studio_credit_cost

DEMO_USAGE_KIND = "demo_studio_image"

# Основная генерация картинок (промпт + WaveSpeed/Grok в одной строке истории).
STUDIO_IMAGE_USAGE_KIND = "studio_image"

# Старые списания под этим kind больше не показываем пользователю в истории.
USER_HIDDEN_CREDIT_HISTORY_KINDS = frozenset({"studio_prompt_refine"})

DEMO_ELIGIBLE_USAGE_KINDS = frozenset(
    {
        STUDIO_IMAGE_USAGE_KIND,
        "studio_prompt_refine",
        "studio_inpaint",
        # Первый кадр video = полноценная image-генерация (Grok + WaveSpeed).
        "studio_motion_first_frame",
        # Bootstrap kinds: demo only for non-Credits plans; Credits uses free onboarding or paid credits.
        "studio_model_bootstrap_face_merge",
        "studio_model_bootstrap_body_compose",
        "studio_model_bootstrap_sheet",
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


def demo_slot_reserved_from_params(params: dict[str, Any] | None) -> bool:
    if not params:
        return False
    return str(params.get("demo_slot_reserved") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def demo_slot_released_from_params(params: dict[str, Any] | None) -> bool:
    if not params:
        return False
    return str(params.get("demo_slot_released") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def demo_generations_grant() -> int:
    return max(0, int(settings.demo_generations_grant))


def effective_demo_remaining_for_access(
    demo_remaining: int,
    *,
    demo_slot_reserved: bool = False,
) -> int:
    """Учитывает слот, уже зарезервированный при accept job (баланс в БД уже уменьшен)."""
    rem = max(0, int(demo_remaining))
    if demo_slot_reserved and rem <= 0:
        return 1
    return rem


async def release_reserved_demo_slot(
    session: AsyncSession,
    *,
    owner_id: int,
    device_signal: DeviceSignal | None = None,
) -> bool:
    """Вернуть демо-слот, зарезервированный при accept job, если задача упала."""
    acc = await _credit_account_for_update(session, owner_id)
    if acc is None:
        return False
    cap = demo_generations_grant()
    before = int(acc.demo_generations_remaining or 0)
    if before >= cap:
        return False
    acc.demo_generations_remaining = min(cap, before + 1)
    await session.flush()
    return True


MODEL_PROFILE_GEN_KIND = "studio_model_profile_generate"


async def owner_used_model_profile_generation(
    session: AsyncSession, owner_id: int
) -> bool:
    row = (
        await session.execute(
            select(UsageEvent.id)
            .where(
                UsageEvent.user_id == owner_id,
                UsageEvent.kind == MODEL_PROFILE_GEN_KIND,
            )
            .limit(1)
        )
    ).first()
    return row is not None


def model_profile_generation_free(
    *,
    plan: str,
    demo_remaining: int,
    prior_profile_generation: bool,
) -> bool:
    """Первая генерация описания по фото — бесплатно; на Credits также пока есть демо."""
    if not prior_profile_generation:
        return True
    return is_credits_plan(plan) and demo_remaining > 0


def onboarding_wizard_profile_free(
    *,
    plan: str,
    demo_remaining: int,
    onboarding_wizard: bool,
) -> bool:
    """Legacy: визард передаёт onboarding_wizard=1 — бесплатно на Credits с демо."""
    if not onboarding_wizard:
        return False
    if not is_credits_plan(plan):
        return False
    return demo_remaining > 0


def parse_onboarding_wizard_flag(raw: str | bool | None) -> bool:
    if isinstance(raw, bool):
        return raw
    return str(raw or "").strip().lower() in ("1", "true", "yes", "on")


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


async def _credit_account_for_update(
    session: AsyncSession,
    user_id: int,
) -> CreditAccount | None:
    stmt = (
        select(CreditAccount)
        .where(CreditAccount.user_id == user_id)
        .with_for_update()
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def assert_studio_image_billing_available(
    session: AsyncSession,
    actor: User,
    billing_owner: User,
    *,
    plan: str,
    usage_kind: str,
    quoted_cost: int,
    wave_model_id: str | None = None,
    grok_pipeline: str = "standard",
    wave_profile: str | None = "nsfw",
    wan_edit_tier: str | None = "standard",
    device_signal: DeviceSignal | None = None,
) -> None:
    """Проверка доступности оплаты без списания (перед постановкой job в очередь)."""
    if not studio_charges_credits(plan):
        return
    cost = apply_studio_credit_cost(plan, quoted_cost)
    if cost <= 0:
        return
    acc = await session.get(CreditAccount, billing_owner.id)
    demo_rem = int(acc.demo_generations_remaining) if acc is not None else 0
    credits = int(acc.balance) if acc is not None else 0
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
        return
    if demo_rem <= 0 and credits <= 0:
        raise_studio_access_denied(demo_remaining=demo_rem, credits=credits)
    await ensure_can_consume_credits(session, actor, cost)


async def admin_adjust_demo_generations(
    session: AsyncSession,
    *,
    billing_user_id: int,
    delta: int,
    admin_user_id: int,
    note: str | None,
) -> int:
    """Ручное изменение остатка демо-генераций владельца workspace."""
    if delta == 0:
        raise ValueError("delta must be non-zero")
    acc = await _credit_account_for_update(session, billing_user_id)
    if acc is None:
        acc = CreditAccount(user_id=billing_user_id, balance=0, demo_generations_remaining=0)
        session.add(acc)
        await session.flush()
    before = int(acc.demo_generations_remaining or 0)
    new_val = max(0, before + delta)
    acc.demo_generations_remaining = new_val
    meta = {"by_admin": admin_user_id, "note": (note or "")[:2000], "delta": delta}
    session.add(
        UsageEvent(
            user_id=billing_user_id,
            kind="admin_demo_generations_adjustment",
            credits_delta=0,
            meta=json.dumps(meta, ensure_ascii=False),
        )
    )
    await session.flush()
    return new_val


async def reserve_studio_image_demo_slot(
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
    device_signal: DeviceSignal | None = None,
) -> bool:
    """
    Резервирует демо-слот при принятии job (до постановки в очередь).
    Возвращает True, если списан демо-слот; иначе проверяет кредиты (402).
    """
    billing, cost, used_demo = await prepare_studio_image_billing(
        session,
        actor,
        billing,
        plan=plan,
        base_cost=base_cost,
        usage_kind=usage_kind,
        quoted_cost=quoted_cost,
        wave_model_id=wave_model_id,
        grok_pipeline=grok_pipeline,
        wave_profile=wave_profile,
        wan_edit_tier=wan_edit_tier,
        device_signal=device_signal,
        lock_account=True,
    )
    if used_demo:
        return True
    await ensure_can_consume_credits(session, actor, cost)
    return False


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
    device_signal: DeviceSignal | None = None,
    lock_account: bool = False,
    demo_slot_reserved: bool = False,
) -> tuple[User, int, bool]:
    """
    Демо-счётчик или кредиты. quoted_cost — из studio_image_pricing; иначе base_cost.
    """
    if demo_slot_reserved:
        return billing, 0, True

    if not studio_charges_credits(plan):
        return billing, 0, False

    cost = apply_studio_credit_cost(plan, quoted_cost if quoted_cost is not None else base_cost)
    if cost <= 0:
        return billing, 0, False

    # Не трогаем billing.credit_account лениво — async session + greenlet_spawn.
    if lock_account:
        acc = await _credit_account_for_update(session, billing.id)
    else:
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
        # Account demo balance is authoritative; device cap applies only at signup grant.
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


async def prepare_bootstrap_image_billing(
    session: AsyncSession,
    actor: User,
    billing_owner: User,
    *,
    plan: str,
    usage_kind: str,
    wave_model_id: str,
    device_signal: DeviceSignal | None = None,
    lock_account: bool = False,
    demo_slot_reserved: bool = False,
) -> tuple[User, int, bool]:
    """Биллинг bootstrap-генераций (face/body/sheet) с учётом демо-слотов."""
    quoted = quote_studio_image_credits(
        wave_model_id=wave_model_id,
        wan_edit_tier="standard",
        grok_pipeline="none",
    )
    return await prepare_studio_image_billing(
        session,
        actor,
        billing_owner,
        plan=plan,
        base_cost=quoted,
        usage_kind=usage_kind,
        quoted_cost=quoted,
        wave_model_id=wave_model_id,
        grok_pipeline="none",
        wave_profile="nsfw",
        wan_edit_tier="standard",
        device_signal=device_signal,
        lock_account=lock_account,
        demo_slot_reserved=demo_slot_reserved,
    )


async def reserve_bootstrap_image_demo_slot(
    session: AsyncSession,
    actor: User,
    billing_owner: User,
    *,
    plan: str,
    usage_kind: str,
    wave_model_id: str,
    device_signal: DeviceSignal | None = None,
) -> bool:
    """Резервирует демо-слот для bootstrap при accept job."""
    billing, cost, used_demo = await prepare_bootstrap_image_billing(
        session,
        actor,
        billing_owner,
        plan=plan,
        usage_kind=usage_kind,
        wave_model_id=wave_model_id,
        device_signal=device_signal,
        lock_account=True,
    )
    if used_demo:
        return True
    if cost <= 0:
        return False
    await ensure_can_consume_credits(session, actor, cost)
    return False
