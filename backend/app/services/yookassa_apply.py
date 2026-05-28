from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.billing_credits import (
    assert_credits_quantity_allowed,
    credits_total_rub,
    legacy_pack_total_rub,
)
from app.db.models import (
    CreditAccount,
    Subscription,
    SubscriptionStatus,
    UsageEvent,
    User,
    YookassaProcessedPayment,
)
from app.services.billing_plan import (
    BILLING_PLAN_BYOK,
    BILLING_PLAN_MANAGED,
    normalize_billing_plan,
    platform_covers_studio_api_costs,
)
from app.services.entitlements import subscription_is_paid_active
from app.services.plan_catalog import get_plan_spec, managed_period_credits, resolve_product_id
from app.services.plan_entitlements import subscription_period_days
from app.services.referral import grant_referrer_reward_if_needed

log = logging.getLogger(__name__)


def _period_end(product: str) -> datetime:
    days = subscription_period_days(product)
    return datetime.now(timezone.utc) + timedelta(days=days)


async def apply_yookassa_payment_succeeded(
    session: AsyncSession,
    *,
    payment_object: dict[str, Any],
) -> dict[str, Any]:
    """Обработать успешный платёж (вебхук). Возвращает краткий результат для лога."""
    pid = str(payment_object.get("id") or "").strip()
    if not pid:
        return {"ok": False, "error": "no payment id"}

    existing = await session.get(YookassaProcessedPayment, pid)
    if existing:
        return {"ok": True, "skipped": "duplicate", "payment_id": pid}

    meta_raw = payment_object.get("metadata")
    meta: dict[str, str] = {}
    if isinstance(meta_raw, dict):
        meta = {str(k): str(v) for k, v in meta_raw.items()}

    uid_s = (meta.get("user_id") or "").strip()
    product = (meta.get("product") or "").strip()
    if not uid_s or not product:
        log.warning("yookassa: missing metadata user_id/product for payment %s", pid)
        return {"ok": False, "error": "metadata"}

    try:
        user_id = int(uid_s)
    except ValueError:
        return {"ok": False, "error": "bad user_id"}

    user = await session.get(User, user_id)
    if not user:
        return {"ok": False, "error": "user not found"}

    owner = user
    if user.parent_user_id is not None:
        parent = await session.get(User, user.parent_user_id)
        if not parent:
            return {"ok": False, "error": "parent missing"}
        owner = parent

    billing_uid = owner.id
    stmt = select(Subscription).where(Subscription.user_id == billing_uid)
    sub = (await session.execute(stmt)).scalar_one_or_none()
    if not sub:
        sub = Subscription(user_id=billing_uid, status=SubscriptionStatus.none)
        session.add(sub)
        await session.flush()

    session.add(YookassaProcessedPayment(payment_id=pid))

    resolved = resolve_product_id(product)
    spec = get_plan_spec(resolved)
    if spec is not None:
        sub.billing_plan = spec.billing_plan
        sub.plan_tier = spec.tier
        sub.status = SubscriptionStatus.active
        sub.current_period_end = _period_end(resolved)
        bonus = 0
        period_bonus = managed_period_credits(spec)
        if period_bonus > 0:
            bonus = period_bonus
            acc = await session.get(CreditAccount, billing_uid)
            if acc is None:
                acc = CreditAccount(user_id=billing_uid, balance=0)
                session.add(acc)
                await session.flush()
            acc.balance += bonus
            session.add(
                UsageEvent(
                    user_id=billing_uid,
                    kind="yookassa_managed_subscription_bonus",
                    credits_delta=bonus,
                    meta=json.dumps(
                        {
                            "payment_id": pid,
                            "product": resolved,
                            "tier": spec.tier,
                        },
                        ensure_ascii=False,
                    ),
                )
            )
        await grant_referrer_reward_if_needed(session, billing_uid)
        await session.commit()
        return {
            "ok": True,
            "payment_id": pid,
            "granted": resolved,
            "credits_bonus": bonus,
        }

    if product == "credits_pack":
        q_raw = (meta.get("credits_quantity") or "").strip()
        if q_raw:
            try:
                n = int(q_raw)
            except ValueError:
                log.warning("yookassa: bad credits_quantity for payment %s", pid)
                await session.commit()
                return {"ok": False, "error": "credits_quantity"}
            try:
                assert_credits_quantity_allowed(n)
            except ValueError as e:
                log.warning("yookassa: credits quantity invalid payment %s: %s", pid, e)
                await session.commit()
                return {"ok": False, "error": "credits_quantity_range"}
            expected = credits_total_rub(n)
        else:
            n = max(1, int(settings.billing_credit_pack_credits))
            expected = legacy_pack_total_rub()

        amount_raw = payment_object.get("amount")
        paid = Decimal("0")
        if isinstance(amount_raw, dict):
            paid = Decimal(str(amount_raw.get("value") or "0")).quantize(Decimal("0.01"), ROUND_HALF_UP)
        if paid != expected:
            log.error(
                "yookassa: amount mismatch payment %s paid=%s expected=%s credits=%s",
                pid,
                paid,
                expected,
                n,
            )
            await session.commit()
            return {"ok": False, "error": "amount_mismatch", "payment_id": pid}

        acc = await session.get(CreditAccount, billing_uid)
        if acc is None:
            acc = CreditAccount(user_id=billing_uid, balance=0)
            session.add(acc)
            await session.flush()

        plan_norm = normalize_billing_plan(sub.billing_plan)
        if not subscription_is_paid_active(sub) or not platform_covers_studio_api_costs(plan_norm):
            log.warning(
                "yookassa: credits_pack rejected — no paid Managed subscription user=%s payment=%s",
                billing_uid,
                pid,
            )
            await session.rollback()
            return {"ok": False, "error": "subscription_required", "payment_id": pid}

        acc.balance += n
        ev = UsageEvent(
            user_id=billing_uid,
            kind="yookassa_credits_pack",
            credits_delta=n,
            meta=json.dumps(
                {"payment_id": pid, "product": product, "credits_quantity": n},
                ensure_ascii=False,
            ),
        )
        session.add(ev)
        await session.commit()
        return {"ok": True, "payment_id": pid, "granted": "credits", "amount": n}

    log.warning("yookassa: unknown product %s payment %s", product, pid)
    await session.commit()
    return {"ok": False, "error": "unknown product"}
