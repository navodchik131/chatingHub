"""Обработка webhook Tribute (платформа) → подписка / кредиты."""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.connectors.tribute.handlers import _external_event_id, _norm_event_name
from app.db.models import (
    CreditAccount,
    Subscription,
    SubscriptionStatus,
    TributeProcessedEvent,
    UsageEvent,
)
from app.services.billing_credits import assert_credits_quantity_allowed, credits_total_rub
from app.services.billing_plan import is_credits_plan, is_standard_plan, normalize_billing_plan, platform_covers_studio_api_costs
from app.services.billing_subscription import activate_subscription_product, subscription_period_end
from app.services.entitlements import subscription_is_paid_active
from app.services.plan_catalog import get_plan_spec, resolve_product_id
from app.services.referral import grant_referrer_reward_if_needed
from app.services.studio_workflow_defaults import provision_full_workflow_workspaces
from app.services.creator_donation_apply import apply_creator_donation_webhook
from app.services.telegram_identity import find_owner_by_telegram_id
from app.services.tribute_billing_catalog import TributeBillingCatalog, TributeBillingTarget, parse_tribute_billing_catalog

log = logging.getLogger(__name__)

_DIGITAL_EVENTS = frozenset({"newdigitalproduct"})
_SUB_NEW_EVENTS = frozenset({"newsubscription"})
_SUB_RENEW_EVENTS = frozenset({"renewedsubscription"})
_SUB_CANCEL_EVENTS = frozenset({"cancelledsubscription"})


def tribute_billing_catalog() -> TributeBillingCatalog:
    return parse_tribute_billing_catalog(settings.tribute_billing_product_map_json)


def _payload(body: dict[str, Any]) -> dict[str, Any]:
    p = body.get("payload")
    return p if isinstance(p, dict) else {}


def _telegram_user_id(payload: dict[str, Any]) -> int | None:
    for key in ("telegram_user_id", "telegramUserId", "user_telegram_id"):
        raw = payload.get(key)
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                continue
    return None


def _product_id(payload: dict[str, Any]) -> int | None:
    for key in ("product_id", "productId"):
        raw = payload.get(key)
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                continue
    return None


def _subscription_id(payload: dict[str, Any]) -> int | None:
    for key in ("subscription_id", "subscriptionId"):
        raw = payload.get(key)
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                continue
    return None


def _amount_rub_from_payload(payload: dict[str, Any], *, fallback_rub: int) -> int:
    amount = payload.get("amount") or payload.get("price")
    currency = str(payload.get("currency") or "rub").upper()
    try:
        minor = int(amount)
    except (TypeError, ValueError):
        return fallback_rub
    if currency in ("RUB", "RUR"):
        return max(0, minor // 100) if minor > 1000 else max(0, minor)
    return fallback_rub


async def _grant_credits_pack(
    session: AsyncSession,
    *,
    billing_uid: int,
    credits_quantity: int,
    payment_ref: str,
    amount_rub: int,
) -> dict[str, Any]:
    sub = await session.scalar(select(Subscription).where(Subscription.user_id == billing_uid))
    if sub is None:
        sub = Subscription(user_id=billing_uid, status=SubscriptionStatus.none)
        session.add(sub)
        await session.flush()

    plan_norm = normalize_billing_plan(sub.billing_plan)
    credits_plan_topup = is_credits_plan(plan_norm)
    if not credits_plan_topup and (
        not subscription_is_paid_active(sub) or not platform_covers_studio_api_costs(plan_norm)
    ):
        return {"ok": False, "error": "subscription_required", "payment_ref": payment_ref}

    try:
        assert_credits_quantity_allowed(credits_quantity)
    except ValueError as e:
        return {"ok": False, "error": str(e), "payment_ref": payment_ref}

    acc = await session.get(CreditAccount, billing_uid)
    if acc is None:
        acc = CreditAccount(user_id=billing_uid, balance=0)
        session.add(acc)
        await session.flush()

    acc.balance += credits_quantity
    session.add(
        UsageEvent(
            user_id=billing_uid,
            kind="tribute_credits_pack",
            credits_delta=credits_quantity,
            meta=json.dumps(
                {
                    "payment_ref": payment_ref,
                    "credits_quantity": credits_quantity,
                    "amount_rub": amount_rub,
                },
                ensure_ascii=False,
            ),
        )
    )
    await grant_referrer_reward_if_needed(
        session,
        billing_uid,
        trigger_product="credits_pack",
        payment_amount_rub=Decimal(amount_rub),
    )
    await provision_full_workflow_workspaces(session, owner_id=billing_uid)
    return {"ok": True, "granted": "credits", "amount": credits_quantity}


async def _apply_target(
    session: AsyncSession,
    *,
    billing_uid: int,
    target: TributeBillingTarget,
    payment_ref: str,
    amount_rub: int,
) -> dict[str, Any]:
    product = resolve_product_id(target.product)
    if product == "credits_pack" or target.credits_quantity is not None:
        q = int(target.credits_quantity or 0)
        if q <= 0:
            return {"ok": False, "error": "credits_quantity"}
        return await _grant_credits_pack(
            session,
            billing_uid=billing_uid,
            credits_quantity=q,
            payment_ref=payment_ref,
            amount_rub=amount_rub or credits_total_rub(q),
        )

    spec = get_plan_spec(product)
    if spec is None:
        return {"ok": False, "error": "unknown product", "product": product}

    paid_rub = amount_rub if amount_rub > 0 else spec.price_rub
    result = await activate_subscription_product(
        session,
        billing_uid,
        product,
        payment_ref=payment_ref,
        payment_kind="tribute",
        payment_amount_rub=paid_rub,
    )
    await provision_full_workflow_workspaces(session, owner_id=billing_uid)
    return {
        "ok": True,
        "granted": result["product"],
        "credits_bonus": result["managed_bonus_credits"],
    }


async def _extend_subscription_period(
    session: AsyncSession,
    *,
    billing_uid: int,
    target: TributeBillingTarget,
    payment_ref: str,
) -> dict[str, Any]:
    product = resolve_product_id(target.product)
    spec = get_plan_spec(product)
    if spec is None:
        return {"ok": False, "error": "unknown product", "product": product}

    sub = await session.scalar(select(Subscription).where(Subscription.user_id == billing_uid))
    if sub is None:
        sub = Subscription(user_id=billing_uid, status=SubscriptionStatus.none)
        session.add(sub)
        await session.flush()

    sub.billing_plan = spec.billing_plan
    sub.plan_tier = spec.tier
    sub.status = SubscriptionStatus.active
    sub.current_period_end = subscription_period_end(product)

    session.add(
        UsageEvent(
            user_id=billing_uid,
            kind="tribute_subscription_renewed",
            credits_delta=0,
            meta=json.dumps(
                {"payment_ref": payment_ref, "product": product},
                ensure_ascii=False,
            ),
        )
    )
    await provision_full_workflow_workspaces(session, owner_id=billing_uid)
    return {"ok": True, "granted": product, "renewed": True}


async def apply_tribute_billing_webhook(
    session: AsyncSession,
    *,
    body: dict[str, Any],
    catalog: TributeBillingCatalog | None = None,
) -> dict[str, Any]:
    cat = catalog or tribute_billing_catalog()
    name_raw = str(body.get("name") or "").strip()
    if not name_raw:
        return {"ok": True, "skipped": "no_event_name"}

    norm = _norm_event_name(name_raw)
    payload = _payload(body)

    if norm in frozenset({"newdonation", "recurrentdonation", "cancelleddonation"}):
        return await apply_creator_donation_webhook(session, body=body)

    tg_id = _telegram_user_id(payload)
    if tg_id is None:
        log.warning("tribute billing webhook: no telegram_user_id event=%s", name_raw)
        return {"ok": False, "error": "no_telegram_user_id"}

    owner = await find_owner_by_telegram_id(session, tg_id)
    if not owner:
        log.warning("tribute billing webhook: owner not found tg=%s event=%s", tg_id, name_raw)
        return {"ok": False, "error": "owner_not_found", "telegram_user_id": tg_id}

    external_id = _external_event_id(0, body)
    external_id = f"platform:{external_id}"
    existing = await session.scalar(
        select(TributeProcessedEvent.id).where(TributeProcessedEvent.external_event_id == external_id)
    )
    if existing:
        return {"ok": True, "duplicate": external_id}

    billing_uid = owner.id
    payment_ref = external_id

    if norm in _DIGITAL_EVENTS:
        pid = _product_id(payload)
        if pid is None:
            return {"ok": False, "error": "no_product_id"}
        target = cat.target_for_digital_product(pid)
        if target is None:
            log.warning("tribute billing: unmapped product_id=%s", pid)
            return {"ok": False, "error": "unmapped_product", "product_id": pid}
        fallback_rub = 0
        spec = get_plan_spec(target.product)
        if spec:
            fallback_rub = spec.price_rub
        elif target.credits_quantity:
            fallback_rub = credits_total_rub(target.credits_quantity)
        amount_rub = _amount_rub_from_payload(payload, fallback_rub=fallback_rub)
        result = await _apply_target(
            session,
            billing_uid=billing_uid,
            target=target,
            payment_ref=payment_ref,
            amount_rub=amount_rub,
        )
    elif norm in _SUB_NEW_EVENTS or norm in _SUB_RENEW_EVENTS:
        sid = _subscription_id(payload)
        if sid is None:
            return {"ok": False, "error": "no_subscription_id"}
        target = cat.target_for_subscription(sid)
        if target is None:
            return {"ok": False, "error": "unmapped_subscription", "subscription_id": sid}
        if norm in _SUB_NEW_EVENTS:
            spec = get_plan_spec(target.product)
            amount_rub = _amount_rub_from_payload(payload, fallback_rub=spec.price_rub if spec else 0)
            result = await _apply_target(
                session,
                billing_uid=billing_uid,
                target=target,
                payment_ref=payment_ref,
                amount_rub=amount_rub,
            )
        else:
            result = await _extend_subscription_period(
                session,
                billing_uid=billing_uid,
                target=target,
                payment_ref=payment_ref,
            )
    elif norm in _SUB_CANCEL_EVENTS:
        sub = await session.scalar(select(Subscription).where(Subscription.user_id == billing_uid))
        if sub and sub.status == SubscriptionStatus.active:
            sub.status = SubscriptionStatus.canceled
        result = {"ok": True, "canceled": True}
    else:
        return {"ok": True, "skipped": norm}

    if result.get("ok"):
        session.add(
            TributeProcessedEvent(
                external_event_id=external_id,
                event_name=name_raw,
                user_id=billing_uid,
                telegram_user_id=tg_id,
                result_json=json.dumps(result, ensure_ascii=False)[:4000],
            )
        )
        await session.commit()
    else:
        await session.rollback()

    log.info("tribute billing webhook user=%s event=%s result=%s", billing_uid, name_raw, result)
    return result
