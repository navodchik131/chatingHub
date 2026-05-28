from __future__ import annotations

import json
import logging
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
    normalize_billing_plan,
    platform_covers_studio_api_costs,
)
from app.services.billing_subscription import activate_subscription_product
from app.services.entitlements import subscription_is_paid_active
from app.services.plan_catalog import get_plan_spec, resolve_product_id
from app.services.referral import grant_referrer_reward_if_needed

log = logging.getLogger(__name__)


def _payment_amount_rub(payment_object: dict[str, Any]) -> Decimal:
    amount_raw = payment_object.get("amount")
    if isinstance(amount_raw, dict):
        return Decimal(str(amount_raw.get("value") or "0")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    return Decimal(0)


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

    paid_rub = _payment_amount_rub(payment_object)
    resolved = resolve_product_id(product)
    spec = get_plan_spec(resolved)
    if spec is not None:
        amount_rub = int(paid_rub) if paid_rub > 0 else spec.price_rub
        result = await activate_subscription_product(
            session,
            billing_uid,
            resolved,
            payment_ref=pid,
            payment_kind="yookassa",
            payment_amount_rub=amount_rub,
        )
        await session.commit()
        return {
            "ok": True,
            "payment_id": pid,
            "granted": result["product"],
            "credits_bonus": result["managed_bonus_credits"],
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

        if paid_rub != expected:
            log.error(
                "yookassa: amount mismatch payment %s paid=%s expected=%s credits=%s",
                pid,
                paid_rub,
                expected,
                n,
            )
            await session.commit()
            return {"ok": False, "error": "amount_mismatch", "payment_id": pid}

        plan_norm = normalize_billing_plan(sub.billing_plan)
        if not subscription_is_paid_active(sub) or not platform_covers_studio_api_costs(plan_norm):
            log.warning(
                "yookassa: credits_pack rejected — no paid Managed subscription user=%s payment=%s",
                billing_uid,
                pid,
            )
            await session.rollback()
            return {"ok": False, "error": "subscription_required", "payment_id": pid}

        acc = await session.get(CreditAccount, billing_uid)
        if acc is None:
            acc = CreditAccount(user_id=billing_uid, balance=0)
            session.add(acc)
            await session.flush()

        acc.balance += n
        session.add(
            UsageEvent(
                user_id=billing_uid,
                kind="yookassa_credits_pack",
                credits_delta=n,
                meta=json.dumps(
                    {"payment_id": pid, "product": product, "credits_quantity": n},
                    ensure_ascii=False,
                ),
            )
        )
        await grant_referrer_reward_if_needed(
            session,
            billing_uid,
            trigger_product="credits_pack",
            payment_amount_rub=paid_rub,
        )
        await session.commit()
        return {"ok": True, "payment_id": pid, "granted": "credits", "amount": n}

    log.warning("yookassa: unknown product %s payment %s", product, pid)
    await session.commit()
    return {"ok": False, "error": "unknown product"}
