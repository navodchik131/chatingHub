"""Агрегаты для админ-панели платформы."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, time, timezone

from sqlalchemy import func, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Conversation,
    CreditAccount,
    Message,
    StudioGeneration,
    StudioMotionRender,
    Subscription,
    SubscriptionStatus,
    TributeEarningEvent,
    UsageEvent,
    User,
    UserStudioModel,
    UserStudioModelImage,
    YookassaProcessedPayment,
)

# События, не считающиеся «осмысленной» активностью владельца (бонусы при регистрации и т.п.)
_USAGE_KINDS_NOT_ENGAGEMENT = frozenset(
    {"referral_signup_bonus", "managed_subscription_bonus", "standard_subscription_bonus"}
)

_PAID_SUBSCRIPTION_STATUSES = (
    SubscriptionStatus.active,
    SubscriptionStatus.trialing,
    SubscriptionStatus.past_due,
)


def _day_key(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date().isoformat()


def _pct(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * part / total, 1)


def _owner_id_expr():
    """ID владельца пространства для строки users (владелец или участник)."""
    return func.coalesce(User.parent_user_id, User.id)


async def _count_distinct_active_owners(
    session: AsyncSession, since: datetime
) -> int:
    usage_owners = (
        select(_owner_id_expr().label("oid"))
        .select_from(UsageEvent)
        .join(User, User.id == UsageEvent.user_id)
        .where(UsageEvent.created_at >= since)
    )
    studio_owners = select(StudioGeneration.user_id.label("oid")).where(
        StudioGeneration.created_at >= since
    )
    chat_owners = (
        select(Conversation.user_id.label("oid"))
        .select_from(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Message.created_at >= since)
    )
    combined = union_all(usage_owners, studio_owners, chat_owners).subquery()
    return int(
        await session.scalar(
            select(func.count(func.distinct(combined.c.oid))).select_from(combined)
        )
        or 0
    )


async def _count_engaged_owners_ever(session: AsyncSession) -> int:
    """Владельцы с хотя бы одной осмысленной активностью (чаты, студия, usage)."""
    usage_owners = (
        select(_owner_id_expr().label("oid"))
        .select_from(UsageEvent)
        .join(User, User.id == UsageEvent.user_id)
        .where(~UsageEvent.kind.in_(_USAGE_KINDS_NOT_ENGAGEMENT))
    )
    studio_owners = select(StudioGeneration.user_id.label("oid"))
    chat_owners = (
        select(Conversation.user_id.label("oid"))
        .select_from(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
    )
    combined = union_all(usage_owners, studio_owners, chat_owners).subquery()
    return int(
        await session.scalar(
            select(func.count(func.distinct(combined.c.oid))).select_from(combined)
        )
        or 0
    )


async def _build_engagement_stats(session: AsyncSession, owners: int) -> dict:
    now = datetime.now(timezone.utc)
    since_7 = now - timedelta(days=7)
    since_30 = now - timedelta(days=30)

    active_7d = await _count_distinct_active_owners(session, since_7)
    active_30d = await _count_distinct_active_owners(session, since_30)

    paid_active = int(
        await session.scalar(
            select(func.count(Subscription.id))
            .join(User, User.id == Subscription.user_id)
            .where(
                User.parent_user_id.is_(None),
                Subscription.status == SubscriptionStatus.active,
                or_(
                    Subscription.current_period_end.is_(None),
                    Subscription.current_period_end >= now,
                ),
            )
        )
        or 0
    )
    trialing = int(
        await session.scalar(
            select(func.count(Subscription.id))
            .join(User, User.id == Subscription.user_id)
            .where(
                User.parent_user_id.is_(None),
                Subscription.status == SubscriptionStatus.trialing,
            )
        )
        or 0
    )
    past_due = int(
        await session.scalar(
            select(func.count(Subscription.id))
            .join(User, User.id == Subscription.user_id)
            .where(
                User.parent_user_id.is_(None),
                Subscription.status == SubscriptionStatus.past_due,
            )
        )
        or 0
    )
    paid_or_due = int(
        await session.scalar(
            select(func.count(Subscription.id))
            .join(User, User.id == Subscription.user_id)
            .where(
                User.parent_user_id.is_(None),
                Subscription.status.in_(_PAID_SUBSCRIPTION_STATUSES),
            )
        )
        or 0
    )

    engaged_ever = await _count_engaged_owners_ever(session)
    zombie = max(0, owners - engaged_ever)

    yookassa_buyers = int(
        await session.scalar(
            select(func.count(func.distinct(_owner_id_expr())))
            .select_from(UsageEvent)
            .join(User, User.id == UsageEvent.user_id)
            .where(UsageEvent.kind == "yookassa_credits_pack")
        )
        or 0
    )

    owners_with_studio = int(
        await session.scalar(
            select(func.count(func.distinct(StudioGeneration.user_id)))
        )
        or 0
    )
    owners_with_chat = int(
        await session.scalar(
            select(func.count(func.distinct(Conversation.user_id)))
            .select_from(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
        )
        or 0
    )

    registered_30d = int(
        await session.scalar(
            select(func.count(User.id)).where(
                User.parent_user_id.is_(None),
                User.created_at >= since_30,
            )
        )
        or 0
    )

    new_paid_30d = int(
        await session.scalar(
            select(func.count(User.id))
            .join(Subscription, Subscription.user_id == User.id)
            .where(
                User.parent_user_id.is_(None),
                User.created_at >= since_30,
                Subscription.status == SubscriptionStatus.active,
                or_(
                    Subscription.current_period_end.is_(None),
                    Subscription.current_period_end >= now,
                ),
            )
        )
        or 0
    )

    return {
        "active_owners_7d": active_7d,
        "active_owners_30d": active_30d,
        "active_owners_7d_pct": _pct(active_7d, owners),
        "active_owners_30d_pct": _pct(active_30d, owners),
        "paid_active_owners": paid_active,
        "paid_active_pct": _pct(paid_active, owners),
        "trialing_owners": trialing,
        "past_due_owners": past_due,
        "paid_or_trialing_owners": paid_or_due,
        "paid_or_trialing_pct": _pct(paid_or_due, owners),
        "zombie_owners": zombie,
        "zombie_pct": _pct(zombie, owners),
        "engaged_owners_ever": engaged_ever,
        "owners_yookassa_credits_buyers": yookassa_buyers,
        "owners_with_studio": owners_with_studio,
        "owners_with_chat": owners_with_chat,
        "registered_owners_30d": registered_30d,
        "new_paid_active_owners_30d": new_paid_30d,
        "new_paid_active_30d_pct": _pct(new_paid_30d, registered_30d),
    }


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
    tribute_events_total = int(
        await session.scalar(select(func.count(TributeEarningEvent.id))) or 0
    )
    today_utc = datetime.now(timezone.utc).date()
    tribute_day_start = datetime.combine(today_utc, time.min, tzinfo=timezone.utc)
    tribute_day_end = datetime.combine(today_utc, time.max, tzinfo=timezone.utc)
    tribute_events_today = int(
        await session.scalar(
            select(func.count(TributeEarningEvent.id)).where(
                TributeEarningEvent.occurred_at >= tribute_day_start,
                TributeEarningEvent.occurred_at <= tribute_day_end,
            )
        )
        or 0
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
            "label": f"{(bp or 'standard').lower()} · {(tier or 'solo').lower()} · "
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

    engagement = await _build_engagement_stats(session, owners)

    return {
        "total_users": total_users,
        "workspace_owners": owners,
        "workspace_members": members,
        "engagement": engagement,
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
        "tribute_events_total": tribute_events_total,
        "tribute_events_today": tribute_events_today,
        "subscriptions_by_status": subscriptions_by_status,
        "subscriptions_by_plan": subscriptions_by_plan,
        "registrations_by_day": _series_last_days(reg_counts, days),
        "generations_by_day": _series_last_days(gen_counts, days),
        "chart_days": days,
    }
