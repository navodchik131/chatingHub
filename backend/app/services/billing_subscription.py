"""Активация подписки (ЮKassa или оплата кредитами)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CreditAccount, Subscription, SubscriptionStatus, UsageEvent
from app.services.billing_credits import rub_to_credits_ceil
from app.services.plan_catalog import get_plan_spec, managed_period_credits, resolve_product_id
from app.services.plan_entitlements import subscription_period_days
from app.services.referral import grant_referrer_reward_if_needed


def subscription_period_end(product: str) -> datetime:
    days = subscription_period_days(product)
    return datetime.now(timezone.utc) + timedelta(days=days)


async def activate_subscription_product(
    session: AsyncSession,
    billing_uid: int,
    product: str,
    *,
    payment_ref: str,
    payment_kind: str,
    payment_amount_rub: int,
) -> dict:
    """
    Выдать подписку и бонус Managed. payment_kind: yookassa | credits.
    Возвращает {product, managed_bonus_credits}.
    """
    resolved = resolve_product_id(product)
    spec = get_plan_spec(resolved)
    if spec is None:
        raise ValueError("unknown product")

    sub = await session.scalar(
        select(Subscription).where(Subscription.user_id == billing_uid)
    )
    if sub is None:
        sub = Subscription(user_id=billing_uid, status=SubscriptionStatus.none)
        session.add(sub)
        await session.flush()

    sub.billing_plan = spec.billing_plan
    sub.plan_tier = spec.tier
    sub.status = SubscriptionStatus.active
    sub.current_period_end = subscription_period_end(resolved)

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
                kind="standard_subscription_bonus",
                credits_delta=bonus,
                meta=json.dumps(
                    {
                        "payment_ref": payment_ref,
                        "payment_kind": payment_kind,
                        "product": resolved,
                        "tier": spec.tier,
                    },
                    ensure_ascii=False,
                ),
            )
        )

    from decimal import Decimal

    await grant_referrer_reward_if_needed(
        session,
        billing_uid,
        trigger_product=resolved,
        payment_amount_rub=Decimal(payment_amount_rub),
    )
    return {
        "product": resolved,
        "managed_bonus_credits": bonus,
        "credits_cost": rub_to_credits_ceil(spec.price_rub),
        "price_rub": spec.price_rub,
    }
