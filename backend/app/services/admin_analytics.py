"""Агрегаты для админ-панели платформы."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Conversation,
    CreatorDonationEvent,
    CreditAccount,
    Message,
    StudioGeneration,
    StudioJob,
    StudioMotionRender,
    Subscription,
    SubscriptionStatus,
    UsageEvent,
    User,
    UserStudioModel,
    UserStudioModelImage,
    YookassaProcessedPayment,
)
from app.services.billing_credits import credits_total_rub, legacy_pack_total_rub
from app.services.plan_catalog import get_plan_spec, resolve_product_id
from app.services.studio_image_pricing import normalize_wave_model_id

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


def _month_key(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m")


def _parse_usage_meta(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _usage_event_revenue_rub(kind: str, meta: dict) -> int:
    if kind == "tribute_credits_pack":
        return max(0, int(meta.get("amount_rub") or 0))
    if kind == "yookassa_credits_pack":
        q_raw = meta.get("credits_quantity")
        try:
            q = int(q_raw) if q_raw is not None else 0
        except (TypeError, ValueError):
            q = 0
        if q > 0:
            return int(credits_total_rub(q))
        return int(legacy_pack_total_rub())
    product = meta.get("product")
    if not product:
        return 0
    if kind == "tribute_subscription_renewed":
        spec = get_plan_spec(resolve_product_id(str(product)))
        return int(spec.price_rub) if spec else 0
    if kind == "standard_subscription_bonus":
        if str(meta.get("payment_kind") or "") != "yookassa":
            return 0
        if not meta.get("payment_ref"):
            return 0
        spec = get_plan_spec(resolve_product_id(str(product)))
        return int(spec.price_rub) if spec else 0
    return 0


def _top_plan_label(billing_plan: str | None, tier: str | None) -> str:
    bp = (billing_plan or "credits").strip().lower()
    t = (tier or "solo").strip().lower().title()
    if bp == "credits":
        return f"Credits · {t}"
    if bp in ("pro", "byok"):
        return f"Pro {t}"
    if bp in ("standard", "managed"):
        return t
    return f"{bp.title()} · {t}"


_ENGINE_LABELS: dict[str, str] = {
    "nano-banana-pro": "Nano Banana Pro",
    "nano-banana-2": "Nano Banana 2",
    "gpt-image-2": "GPT Image",
    "seedream-v5.0-pro": "Seedream 5 Pro",
    "wan-2.7": "Wan 2.7 Pro",
}


def _engine_label(model_id: str) -> str:
    mid = normalize_wave_model_id(model_id)
    return _ENGINE_LABELS.get(mid, mid.replace("-", " ").title())


async def _build_revenue_stats(session: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_end = month_start - timedelta(seconds=1)
    prev_month_start = prev_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    revenue_kinds = (
        "yookassa_credits_pack",
        "tribute_credits_pack",
        "tribute_subscription_renewed",
        "standard_subscription_bonus",
    )
    rows = (
        await session.execute(
            select(UsageEvent.kind, UsageEvent.meta, UsageEvent.created_at).where(
                UsageEvent.kind.in_(revenue_kinds)
            )
        )
    ).all()

    total_rub = 0
    month_rub = 0
    prev_month_rub = 0
    by_month: dict[str, int] = defaultdict(int)
    tribute_payments = 0

    for kind, meta_raw, created_at in rows:
        meta = _parse_usage_meta(meta_raw)
        amount = _usage_event_revenue_rub(str(kind or ""), meta)
        if amount <= 0:
            continue
        total_rub += amount
        if created_at:
            mk = _month_key(created_at)
            by_month[mk] += amount
            if created_at >= month_start:
                month_rub += amount
            elif prev_month_start <= created_at < month_start:
                prev_month_rub += amount
        if kind in ("tribute_credits_pack", "tribute_subscription_renewed"):
            tribute_payments += 1

    donations_total_rub = int(
        await session.scalar(
            select(func.coalesce(func.sum(CreatorDonationEvent.amount_minor), 0)).where(
                CreatorDonationEvent.currency == "RUB"
            )
        )
        or 0
    ) // 100
    donations_count = int(
        await session.scalar(select(func.count(CreatorDonationEvent.id))) or 0
    )

    yookassa_count = int(
        await session.scalar(select(func.count(YookassaProcessedPayment.payment_id))) or 0
    )
    payments_total = yookassa_count + tribute_payments + donations_count

    month_change_pct = 0.0
    if prev_month_rub > 0:
        month_change_pct = round(100.0 * (month_rub - prev_month_rub) / prev_month_rub, 1)
    elif month_rub > 0:
        month_change_pct = 100.0

    month_labels_ru = ["ЯНВ", "ФЕВ", "МАР", "АПР", "МАЙ", "ИЮН", "ИЮЛ", "АВГ", "СЕН", "ОКТ", "НОЯ", "ДЕК"]
    revenue_by_month: list[dict[str, int | str]] = []
    cursor = month_start
    for _ in range(12):
        mk = cursor.strftime("%Y-%m")
        revenue_by_month.insert(
            0,
            {
                "month": mk,
                "label": month_labels_ru[cursor.month - 1],
                "amount_rub": int(by_month.get(mk, 0)),
            },
        )
        if cursor.month == 1:
            cursor = cursor.replace(year=cursor.year - 1, month=12)
        else:
            cursor = cursor.replace(month=cursor.month - 1)

    return {
        "payments_total": payments_total,
        "revenue_total_rub": total_rub + donations_total_rub,
        "revenue_month_rub": month_rub,
        "revenue_month_change_pct": month_change_pct,
        "donations_total_rub": donations_total_rub,
        "donations_count": donations_count,
        "revenue_by_month": revenue_by_month,
    }


async def _build_top_plans(session: AsyncSession) -> list[dict[str, int | str | float]]:
    rows = (
        await session.execute(
            select(
                Subscription.billing_plan,
                Subscription.plan_tier,
                func.count(Subscription.id),
            )
            .join(User, User.id == Subscription.user_id)
            .where(
                User.parent_user_id.is_(None),
                Subscription.status.in_(_PAID_SUBSCRIPTION_STATUSES),
            )
            .group_by(Subscription.billing_plan, Subscription.plan_tier)
        )
    ).all()
    items = [
        {
            "label": _top_plan_label(str(bp or ""), str(tier or "") if tier else None),
            "count": int(c or 0),
        }
        for bp, tier, c in rows
    ]
    items.sort(key=lambda x: -int(x["count"]))
    total = sum(int(x["count"]) for x in items) or 1
    out: list[dict[str, int | str | float]] = []
    for item in items[:8]:
        count = int(item["count"])
        out.append(
            {
                "label": str(item["label"]),
                "count": count,
                "pct": _pct(count, total),
            }
        )
    return out


async def _build_generation_types(
    session: AsyncSession,
    *,
    images: int,
    videos: int,
    motion: int,
) -> list[dict[str, int | str | float]]:
    video_total = videos + motion
    total = max(1, images + video_total)
    return [
        {"label": "images", "count": images, "pct": _pct(images, total), "color": "#D7F452"},
        {"label": "videos", "count": video_total, "pct": _pct(video_total, total), "color": "#C084FC"},
    ]


async def _build_top_engines(session: AsyncSession, *, limit: int = 8) -> list[dict[str, int | str]]:
    gen_rows = (
        await session.execute(
            select(StudioGeneration.studio_job_id).where(
                StudioGeneration.studio_job_id.isnot(None)
            )
        )
    ).all()
    job_ids = sorted({int(r[0]) for r in gen_rows if r[0] is not None})
    counts: dict[str, int] = defaultdict(int)
    if job_ids:
        jobs = (
            await session.execute(select(StudioJob).where(StudioJob.id.in_(job_ids)))
        ).scalars().all()
        job_map = {j.id: j for j in jobs}
        for job_id in job_ids:
            job = job_map.get(job_id)
            if not job:
                counts["wan-2.7"] += 1
                continue
            params = _parse_usage_meta(job.params_json)
            model = normalize_wave_model_id(str(params.get("workflow_wave_model") or "wan-2.7"))
            counts[model] += 1

    orphan_gens = int(
        await session.scalar(
            select(func.count(StudioGeneration.id)).where(
                StudioGeneration.studio_job_id.is_(None),
                or_(
                    StudioGeneration.content_type.is_(None),
                    ~StudioGeneration.content_type.ilike("video/%"),
                ),
            )
        )
        or 0
    )
    if orphan_gens:
        counts["wan-2.7"] += orphan_gens

    motion_total = int(await session.scalar(select(func.count(StudioMotionRender.id))) or 0)
    if motion_total:
        counts["wan-2.7"] += motion_total

    ranked = sorted(counts.items(), key=lambda x: -x[1])[:limit]
    return [{"label": _engine_label(k), "count": v, "model_id": k} for k, v in ranked if v > 0]


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
    revenue = await _build_revenue_stats(session)
    top_plans = await _build_top_plans(session)
    generations_by_type = await _build_generation_types(
        session,
        images=studio_images_total,
        videos=studio_videos_total,
        motion=motion_renders_total,
    )
    top_engines = await _build_top_engines(session)

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
        "payments_total": revenue["payments_total"],
        "revenue_total_rub": revenue["revenue_total_rub"],
        "revenue_month_rub": revenue["revenue_month_rub"],
        "revenue_month_change_pct": revenue["revenue_month_change_pct"],
        "donations_total_rub": revenue["donations_total_rub"],
        "donations_count": revenue["donations_count"],
        "revenue_by_month": revenue["revenue_by_month"],
        "top_plans": top_plans,
        "generations_by_type": generations_by_type,
        "top_engines": top_engines,
        "subscriptions_by_status": subscriptions_by_status,
        "subscriptions_by_plan": subscriptions_by_plan,
        "registrations_by_day": _series_last_days(reg_counts, days),
        "generations_by_day": _series_last_days(gen_counts, days),
        "chart_days": days,
    }
