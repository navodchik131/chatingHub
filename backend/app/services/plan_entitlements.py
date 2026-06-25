"""Лимиты тарифа и проверки при операциях."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Conversation,
    Message,
    Subscription,
    UsageEvent,
    User,
    UserStudioModel,
)
from app.services.billing_plan import (
    is_credits_plan,
    is_pro_plan,
    normalize_billing_plan,
    plan_allows_chat,
)
from app.services.entitlements import subscription_is_paid_active
from app.services.plan_catalog import (
    CREDITS_PLAN_LIMITS,
    PLAN_SPECS,
    PlanLimits,
    PlanSpec,
    TIER_SOLO,
    normalize_plan_tier,
    plan_display_name,
    resolve_product_id,
)

GROK_USAGE_KIND = "grok_prompt_generation"


def month_start_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def effective_plan_spec(sub: Subscription | None) -> PlanSpec:
    if sub is None:
        return PLAN_SPECS["sub_standard_solo_month"]
    tier = normalize_plan_tier(sub.plan_tier)
    bp = normalize_billing_plan(sub.billing_plan)
    if bp == "credits":
        return PLAN_SPECS["sub_standard_solo_month"]
    key = f"sub_{bp}_{tier}_month"
    return PLAN_SPECS.get(key) or PLAN_SPECS["sub_standard_solo_month"]


def plan_limits_for_sub(sub: Subscription | None) -> PlanLimits:
    if sub is not None and is_credits_plan(sub.billing_plan):
        if subscription_is_paid_active(sub):
            return effective_plan_spec(sub).limits
        return CREDITS_PLAN_LIMITS
    return effective_plan_spec(sub).limits


def limits_apply(sub: Subscription | None) -> bool:
    """Лимиты подписки — для оплаченной active; Credits без оплаты — свои лимиты."""
    if sub is not None and is_credits_plan(sub.billing_plan):
        return not subscription_is_paid_active(sub)
    return subscription_is_paid_active(sub)


async def count_workspace_users(session: AsyncSession, owner_id: int) -> int:
    members = int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.parent_user_id == owner_id)
        )
        or 0
    )
    return 1 + members


async def count_studio_models(session: AsyncSession, owner_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(UserStudioModel)
            .where(UserStudioModel.user_id == owner_id)
        )
        or 0
    )


async def count_dialogs_this_month(session: AsyncSession, owner_id: int) -> int:
    start = month_start_utc()
    stmt = (
        select(func.count(func.distinct(Message.conversation_id)))
        .select_from(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.user_id == owner_id,
            Message.created_at >= start,
        )
    )
    return int(await session.scalar(stmt) or 0)


async def count_grok_this_month(session: AsyncSession, owner_id: int) -> int:
    start = month_start_utc()
    return int(
        await session.scalar(
            select(func.count())
            .select_from(UsageEvent)
            .where(
                UsageEvent.user_id == owner_id,
                UsageEvent.kind == GROK_USAGE_KIND,
                UsageEvent.created_at >= start,
            )
        )
        or 0
    )


async def plan_usage_snapshot(session: AsyncSession, owner_id: int, sub: Subscription | None) -> dict:
    lim = plan_limits_for_sub(sub)
    return {
        "users": await count_workspace_users(session, owner_id),
        "models": await count_studio_models(session, owner_id),
        "dialogs_this_month": await count_dialogs_this_month(session, owner_id),
        "grok_this_month": await count_grok_this_month(session, owner_id),
        "limits": {
            "max_users": lim.max_users,
            "max_models": lim.max_models,
            "max_dialogs_per_month": lim.max_dialogs_per_month,
            "max_grok_per_month": lim.max_grok_per_month,
        },
    }


def _limit_http(detail: str) -> HTTPException:
    return HTTPException(status_code=402, detail=detail)


def assert_chat_allowed_for_plan(sub: Subscription | None) -> None:
    plan = normalize_billing_plan(sub.billing_plan if sub else None)
    if not plan_allows_chat(plan):
        raise HTTPException(
            status_code=403,
            detail="Чаты доступны на подписке Standard или Pro. Пополните кредиты или оформите тариф.",
        )
    if sub is not None and is_credits_plan(plan) and not subscription_is_paid_active(sub):
        raise HTTPException(
            status_code=403,
            detail="Чаты доступны на подписке Standard или Pro.",
        )


async def assert_can_add_workspace_member(
    session: AsyncSession, owner: User, sub: Subscription | None
) -> None:
    if is_credits_plan(sub.billing_plan if sub else None) and not subscription_is_paid_active(sub):
        raise _limit_http("Команда доступна на подписке Standard или Pro.")
    if not limits_apply(sub):
        return
    lim = plan_limits_for_sub(sub)
    n = await count_workspace_users(session, owner.id)
    if n >= lim.max_users:
        raise _limit_http(
            f"На тарифе {plan_display_name(sub.billing_plan if sub else None, sub.plan_tier if sub else None)} "
            f"доступно до {lim.max_users} пользователей (включая владельца). Повысьте план."
        )


async def assert_can_create_studio_model(
    session: AsyncSession, owner_id: int, sub: Subscription | None
) -> None:
    lim = plan_limits_for_sub(sub)
    if not limits_apply(sub) and not (
        sub is not None and is_credits_plan(sub.billing_plan) and not subscription_is_paid_active(sub)
    ):
        return
    n = await count_studio_models(session, owner_id)
    if n >= lim.max_models:
        raise _limit_http(
            f"Достигнут лимит моделей ({lim.max_models}) для вашего тарифа. "
            "Удалите лишнюю модель или оформите Standard / Pro."
        )


async def assert_dialog_activity_allowed(
    session: AsyncSession, owner_id: int, sub: Subscription | None
) -> None:
    assert_chat_allowed_for_plan(sub)
    if not limits_apply(sub):
        return
    lim = plan_limits_for_sub(sub)
    if lim.max_dialogs_per_month is None:
        return
    n = await count_dialogs_this_month(session, owner_id)
    if n >= lim.max_dialogs_per_month:
        raise _limit_http(
            f"Исчерпан месячный лимит активных диалогов ({lim.max_dialogs_per_month}). "
            "Повысьте тариф или дождитесь нового месяца."
        )


async def assert_grok_allowed(session: AsyncSession, owner_id: int, sub: Subscription | None) -> None:
    if is_pro_plan(sub.billing_plan if sub else None) and subscription_is_paid_active(sub):
        return
    if not limits_apply(sub):
        return
    lim = plan_limits_for_sub(sub)
    if lim.max_grok_per_month is None:
        return
    n = await count_grok_this_month(session, owner_id)
    if n >= lim.max_grok_per_month:
        raise _limit_http(
            "Исчерпан месячный лимит запросов студии. Повысьте тариф или дождитесь нового месяца."
        )


async def record_grok_usage(session: AsyncSession, owner_id: int, *, source: str) -> None:
    session.add(
        UsageEvent(
            user_id=owner_id,
            kind=GROK_USAGE_KIND,
            credits_delta=0,
            meta=json.dumps({"source": source}, ensure_ascii=False),
        )
    )
    await session.flush()


def subscription_period_days(product: str) -> int:
    spec = PLAN_SPECS.get(resolve_product_id(product))
    if spec and spec.period == "year":
        return 365
    from app.config import settings

    return max(1, int(settings.billing_subscription_period_days or 30))
