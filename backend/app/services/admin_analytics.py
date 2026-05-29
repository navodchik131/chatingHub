"""Агрегаты для админ-панели платформы."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Conversation,
    CreditAccount,
    StudioGeneration,
    StudioMotionRender,
    Subscription,
    SubscriptionStatus,
    UsageEvent,
    User,
    UserStudioModel,
    UserStudioModelImage,
    YookassaProcessedPayment,
)


def _day_key(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date().isoformat()


def _series_last_days(counts: dict[str, int], days: int = 30) -> list[dict[str, int | str]]:
    today = datetime.now(timezone.utc).date()
    out: list[dict[str, int | str]] = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        out.append({"date": d, "count": int(counts.get(d, 0))})
    return out


async def build_admin_dashboard(session: AsyncSession, *, chart_days: int = 30) -> dict:
    days = max(7, min(90, chart_days))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    total_users = int(await session.scalar(select(func.count(User.id))) or 0)
    owners = int(
        await session.scalar(
            select(func.count(User.id)).where(User.parent_user_id.is_(None))
        )
        or 0
    )
    members = max(0, total_users - owners)
    total_credits = int(
        await session.scalar(select(func.coalesce(func.sum(CreditAccount.balance), 0))) or 0
    )
    gen_total = int(
        await session.scalar(select(func.count(StudioGeneration.id))) or 0
    )
    studio_models_total = int(
        await session.scalar(select(func.count(UserStudioModel.id))) or 0
    )
    studio_model_images_total = int(
        await session.scalar(select(func.count(UserStudioModelImage.id))) or 0
    )
    studio_images_total = int(
        await session.scalar(
            select(func.count(StudioGeneration.id)).where(
                or_(
                    StudioGeneration.content_type.is_(None),
                    ~StudioGeneration.content_type.ilike("video/%"),
                )
            )
        )
        or 0
    )
    studio_videos_total = int(
        await session.scalar(
            select(func.count(StudioGeneration.id)).where(
                StudioGeneration.content_type.ilike("video/%")
            )
        )
        or 0
    )
    motion_renders_total = int(
        await session.scalar(select(func.count(StudioMotionRender.id))) or 0
    )
    conversations_total = int(
        await session.scalar(select(func.count(Conversation.id))) or 0
    )
    referrals_total = int(
        await session.scalar(
            select(func.count(User.id)).where(User.referred_by_user_id.isnot(None))
        )
        or 0
    )
    yookassa_payments_total = int(
        await session.scalar(select(func.count(YookassaProcessedPayment.payment_id))) or 0
    )

    kind_rows = (
        await session.execute(
            select(UsageEvent.kind, func.count(UsageEvent.id)).group_by(UsageEvent.kind)
        )
    ).all()
    usage_by_kind: dict[str, int] = {str(k or ""): int(c) for k, c in kind_rows}

    sub_status_rows = (
        await session.execute(
            select(Subscription.status, func.count(Subscription.id)).group_by(
                Subscription.status
            )
        )
    ).all()
    subscriptions_by_status = [
        {"label": (st.value if hasattr(st, "value") else str(st or "none")), "count": int(c)}
        for st, c in sub_status_rows
    ]

    paid_statuses = (
        SubscriptionStatus.active,
        SubscriptionStatus.trialing,
        SubscriptionStatus.past_due,
    )
    plan_rows = (
        await session.execute(
            select(
                Subscription.billing_plan,
                Subscription.plan_tier,
                Subscription.status,
                func.count(Subscription.id),
            )
            .where(Subscription.status.in_(paid_statuses))
            .group_by(
                Subscription.billing_plan,
                Subscription.plan_tier,
                Subscription.status,
            )
        )
    ).all()
    subscriptions_by_plan = [
        {
            "label": f"{(bp or 'managed').lower()} · {(tier or 'solo').lower()} · "
            f"{(st.value if hasattr(st, 'value') else str(st))}",
            "count": int(c),
        }
        for bp, tier, st, c in plan_rows
    ]
    subscriptions_by_plan.sort(key=lambda x: -x["count"])

    reg_rows = (
        await session.execute(
            select(User.created_at).where(
                User.parent_user_id.is_(None),
                User.created_at >= since,
            )
        )
    ).all()
    reg_counts: dict[str, int] = defaultdict(int)
    for (created_at,) in reg_rows:
        if created_at:
            reg_counts[_day_key(created_at)] += 1

    gen_rows = (
        await session.execute(
            select(StudioGeneration.created_at).where(StudioGeneration.created_at >= since)
        )
    ).all()
    gen_counts: dict[str, int] = defaultdict(int)
    for (created_at,) in gen_rows:
        if created_at:
            gen_counts[_day_key(created_at)] += 1

    return {
        "total_users": total_users,
        "workspace_owners": owners,
        "workspace_members": members,
        "total_credits_balance": total_credits,
        "studio_generations_total": gen_total,
        "usage_by_kind": usage_by_kind,
        "studio_models_total": studio_models_total,
        "studio_model_images_total": studio_model_images_total,
        "studio_images_total": studio_images_total,
        "studio_videos_total": studio_videos_total,
        "studio_motion_renders_total": motion_renders_total,
        "conversations_total": conversations_total,
        "referrals_total": referrals_total,
        "yookassa_payments_total": yookassa_payments_total,
        "subscriptions_by_status": subscriptions_by_status,
        "subscriptions_by_plan": subscriptions_by_plan,
        "registrations_by_day": _series_last_days(reg_counts, days),
        "generations_by_day": _series_last_days(gen_counts, days),
        "chart_days": days,
    }
