"""Списки пользователей / платежей для drill-down в админ-аналитике."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Conversation,
    Message,
    StudioGeneration,
    Subscription,
    SubscriptionStatus,
    TributeEarningEvent,
    UsageEvent,
    User,
    YookassaProcessedPayment,
)
from app.services.admin_analytics import (
    _PAID_SUBSCRIPTION_STATUSES,
    _USAGE_KINDS_NOT_ENGAGEMENT,
    _owner_id_expr,
)

SEGMENT_TITLES: dict[str, str] = {
    "active_7d": "Активны за 7 дней",
    "active_30d": "Активны за 30 дней",
    "paid_active": "Оплаченная подписка (active)",
    "trialing": "Пробный период (trialing)",
    "past_due": "Просрочен платёж (past_due)",
    "paid_or_trialing": "Подписка active / trialing / past_due",
    "zombie": "Без активности (зомби)",
    "engaged_ever": "Активны хотя бы раз",
    "yookassa_credits_buyers": "Покупали кредиты через ЮKassa",
    "owners_with_studio": "Пробовали студию",
    "owners_without_studio": "Не пробовали студию",
    "owners_with_chat": "Писали в чатах",
    "registered_30d": "Регистрации за 30 дней",
    "new_paid_active_30d": "Новые с paid active за 30 дней",
    "yookassa_payments": "Оплаты ЮKassa",
    "tribute_events": "Донаты и платежи Tribute",
    "referrals": "Регистрации по рефералке",
    "workspace_owners": "Владельцы пространств",
}

VALID_ADMIN_SEGMENTS = frozenset(SEGMENT_TITLES.keys())

# Сегменты для email-рассылок (без платёжных строк и служебных списков)
EMAIL_CAMPAIGN_SEGMENTS = frozenset(
    VALID_ADMIN_SEGMENTS - {"yookassa_payments", "tribute_events"}
)


async def _active_owner_ids(session: AsyncSession, since: datetime) -> set[int]:
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
    rows = (await session.execute(select(combined.c.oid).distinct())).all()
    return {int(r[0]) for r in rows if r[0] is not None}


async def _engaged_owner_ids(session: AsyncSession) -> set[int]:
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
    rows = (await session.execute(select(combined.c.oid).distinct())).all()
    return {int(r[0]) for r in rows if r[0] is not None}


async def _yookassa_payment_attributions(
    session: AsyncSession,
) -> dict[str, tuple[int, str]]:
    """payment_id → (owner_id, описание)."""
    out: dict[str, tuple[int, str]] = {}
    rows = (
        await session.execute(
            select(UsageEvent).where(
                UsageEvent.kind.in_(("yookassa_credits_pack", "managed_subscription_bonus"))
            )
        )
    ).scalars().all()
    for ev in rows:
        owner_id = int(ev.user_id)
        u = await session.get(User, owner_id)
        if u and u.parent_user_id is not None:
            owner_id = int(u.parent_user_id)
        raw = ev.meta or ""
        try:
            meta = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            meta = {}
        if not isinstance(meta, dict):
            meta = {}
        pid = str(meta.get("payment_id") or meta.get("payment_ref") or "").strip()
        if not pid:
            continue
        if ev.kind == "yookassa_credits_pack":
            n = meta.get("credits_quantity", "?")
            detail = f"Пакет кредитов: {n} шт."
        else:
            product = meta.get("product") or "подписка"
            tier = meta.get("tier") or ""
            detail = f"Подписка: {product}" + (f" · {tier}" if tier else "")
        out[pid] = (owner_id, detail)
    return out


def _row_from_user(
    u: User,
    *,
    detail: str | None = None,
    occurred_at: datetime | None = None,
    payment_id: str | None = None,
) -> dict:
    sub = u.subscription
    st = sub.status.value if sub else SubscriptionStatus.none.value
    return {
        "user_id": u.id,
        "email": u.email,
        "user_created_at": u.created_at,
        "subscription_status": st,
        "billing_plan": (sub.billing_plan if sub else None) or "managed",
        "plan_tier": sub.plan_tier if sub else None,
        "detail": detail,
        "occurred_at": occurred_at or u.created_at,
        "payment_id": payment_id,
    }


async def _owners_by_ids(
    session: AsyncSession,
    owner_ids: list[int],
    *,
    details: dict[int, str] | None = None,
    occurred: dict[int, datetime] | None = None,
    limit: int,
) -> list[dict]:
    if not owner_ids:
        return []
    ids = owner_ids[:limit]
    stmt = (
        select(User)
        .where(User.id.in_(ids), User.parent_user_id.is_(None))
        .options(selectinload(User.subscription))
        .order_by(User.created_at.desc())
    )
    users = (await session.execute(stmt)).scalars().all()
    by_id = {u.id: u for u in users}
    items: list[dict] = []
    for oid in ids:
        u = by_id.get(oid)
        if not u:
            continue
        items.append(
            _row_from_user(
                u,
                detail=(details or {}).get(oid),
                occurred_at=(occurred or {}).get(oid),
            )
        )
    return items


async def list_admin_segment(
    session: AsyncSession,
    segment: str,
    *,
    limit: int = 200,
) -> dict:
    if segment not in VALID_ADMIN_SEGMENTS:
        raise ValueError(f"unknown segment: {segment}")

    limit = max(1, min(500, limit))
    now = datetime.now(timezone.utc)
    since_7 = now - timedelta(days=7)
    since_30 = now - timedelta(days=30)
    title = SEGMENT_TITLES[segment]

    if segment == "yookassa_payments":
        attr = await _yookassa_payment_attributions(session)
        payments = (
            (
                await session.execute(
                    select(YookassaProcessedPayment)
                    .order_by(YookassaProcessedPayment.created_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        owner_ids = list({attr[p.payment_id][0] for p in payments if p.payment_id in attr})
        stmt = (
            select(User)
            .where(User.id.in_(owner_ids))
            .options(selectinload(User.subscription))
        )
        users_by_id = {
            u.id: u for u in (await session.execute(stmt)).scalars().all()
        }
        items: list[dict] = []
        for pay in payments:
            pid = pay.payment_id
            if pid in attr:
                oid, detail = attr[pid]
                u = users_by_id.get(oid)
                if u:
                    items.append(
                        _row_from_user(
                            u,
                            detail=detail,
                            occurred_at=pay.created_at,
                            payment_id=pid,
                        )
                    )
                    continue
            items.append(
                {
                    "user_id": None,
                    "email": None,
                    "user_created_at": None,
                    "subscription_status": None,
                    "billing_plan": None,
                    "plan_tier": None,
                    "detail": "Пользователь не привязан в usage_events",
                    "occurred_at": pay.created_at,
                    "payment_id": pid,
                }
            )
        return {"segment": segment, "title": title, "total": len(items), "items": items}

    if segment == "tribute_events":
        events = (
            (
                await session.execute(
                    select(TributeEarningEvent)
                    .order_by(TributeEarningEvent.occurred_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        owner_ids = list({int(ev.user_id) for ev in events})
        users_by_id = {
            u.id: u
            for u in (
                await session.execute(
                    select(User)
                    .where(User.id.in_(owner_ids))
                    .options(selectinload(User.subscription))
                )
            )
            .scalars()
            .all()
        }
        items = []
        for ev in events:
            u = users_by_id.get(int(ev.user_id))
            amount = int(ev.amount_minor or 0)
            sign = "+" if amount >= 0 else ""
            cur = str(ev.currency or "USD").upper()
            detail = f"{ev.event_name}: {sign}{amount / 100:.2f} {cur}"
            if u:
                items.append(
                    _row_from_user(
                        u,
                        detail=detail,
                        occurred_at=ev.occurred_at,
                        payment_id=ev.external_event_id,
                    )
                )
            else:
                items.append(
                    {
                        "user_id": int(ev.user_id),
                        "email": None,
                        "user_created_at": None,
                        "subscription_status": None,
                        "billing_plan": None,
                        "plan_tier": None,
                        "detail": detail,
                        "occurred_at": ev.occurred_at,
                        "payment_id": ev.external_event_id,
                    }
                )
        return {"segment": segment, "title": title, "total": len(items), "items": items}

    if segment == "referrals":
        stmt = (
            select(User)
            .where(User.referred_by_user_id.isnot(None))
            .options(selectinload(User.subscription), selectinload(User.parent))
            .order_by(User.created_at.desc())
            .limit(limit)
        )
        users = (await session.execute(stmt)).scalars().all()
        items = []
        for u in users:
            ref_email = None
            if u.referred_by_user_id:
                ref = await session.get(User, u.referred_by_user_id)
                ref_email = ref.email if ref else None
            detail = f"Пригласил: {ref_email or u.referred_by_user_id}"
            items.append(_row_from_user(u, detail=detail))
        return {"segment": segment, "title": title, "total": len(items), "items": items}

    owner_ids: list[int] = []
    details: dict[int, str] = {}

    if segment == "active_7d":
        owner_ids = sorted(await _active_owner_ids(session, since_7), reverse=True)
    elif segment == "active_30d":
        owner_ids = sorted(await _active_owner_ids(session, since_30), reverse=True)
    elif segment == "paid_active":
        rows = (
            await session.execute(
                select(User.id)
                .join(Subscription, Subscription.user_id == User.id)
                .where(
                    User.parent_user_id.is_(None),
                    Subscription.status == SubscriptionStatus.active,
                    or_(
                        Subscription.current_period_end.is_(None),
                        Subscription.current_period_end >= now,
                    ),
                )
                .order_by(Subscription.current_period_end.desc().nullslast())
                .limit(limit)
            )
        ).all()
        owner_ids = [int(r[0]) for r in rows]
    elif segment == "trialing":
        rows = (
            await session.execute(
                select(User.id)
                .join(Subscription, Subscription.user_id == User.id)
                .where(
                    User.parent_user_id.is_(None),
                    Subscription.status == SubscriptionStatus.trialing,
                )
                .order_by(User.created_at.desc())
                .limit(limit)
            )
        ).all()
        owner_ids = [int(r[0]) for r in rows]
    elif segment == "past_due":
        rows = (
            await session.execute(
                select(User.id)
                .join(Subscription, Subscription.user_id == User.id)
                .where(
                    User.parent_user_id.is_(None),
                    Subscription.status == SubscriptionStatus.past_due,
                )
                .order_by(User.created_at.desc())
                .limit(limit)
            )
        ).all()
        owner_ids = [int(r[0]) for r in rows]
    elif segment == "paid_or_trialing":
        rows = (
            await session.execute(
                select(User.id)
                .join(Subscription, Subscription.user_id == User.id)
                .where(
                    User.parent_user_id.is_(None),
                    Subscription.status.in_(_PAID_SUBSCRIPTION_STATUSES),
                )
                .order_by(User.created_at.desc())
                .limit(limit)
            )
        ).all()
        owner_ids = [int(r[0]) for r in rows]
    elif segment == "zombie":
        engaged = await _engaged_owner_ids(session)
        zombie_stmt = select(User.id).where(User.parent_user_id.is_(None))
        if engaged:
            zombie_stmt = zombie_stmt.where(~User.id.in_(engaged))
        rows = (await session.execute(zombie_stmt.order_by(User.created_at.desc()))).all()
        owner_ids = [int(r[0]) for r in rows][:limit]
    elif segment == "engaged_ever":
        owner_ids = sorted(await _engaged_owner_ids(session), reverse=True)[:limit]
    elif segment == "yookassa_credits_buyers":
        rows = (
            await session.execute(
                select(_owner_id_expr().label("oid"), func.max(UsageEvent.created_at))
                .select_from(UsageEvent)
                .join(User, User.id == UsageEvent.user_id)
                .where(UsageEvent.kind == "yookassa_credits_pack")
                .group_by(_owner_id_expr())
                .order_by(func.max(UsageEvent.created_at).desc())
                .limit(limit)
            )
        ).all()
        owner_ids = []
        occurred: dict[int, datetime] = {}
        for oid, at in rows:
            o = int(oid)
            owner_ids.append(o)
            if at:
                occurred[o] = at
        items = await _owners_by_ids(
            session, owner_ids, occurred=occurred, limit=limit
        )
        for it in items:
            uid = it["user_id"]
            if uid and uid not in details:
                ev = (
                    await session.execute(
                        select(UsageEvent)
                        .join(User, User.id == UsageEvent.user_id)
                        .where(
                            UsageEvent.kind == "yookassa_credits_pack",
                            or_(
                                User.id == uid,
                                User.parent_user_id == uid,
                            ),
                        )
                        .order_by(UsageEvent.created_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if ev and ev.meta:
                    try:
                        meta = json.loads(ev.meta)
                        n = meta.get("credits_quantity", "?")
                        it["detail"] = f"Последняя покупка: {n} кредитов"
                    except json.JSONDecodeError:
                        pass
        return {
            "segment": segment,
            "title": title,
            "total": len(items),
            "items": items,
        }
    elif segment == "owners_with_studio":
        rows = (
            await session.execute(
                select(
                    StudioGeneration.user_id,
                    func.count(StudioGeneration.id),
                    func.max(StudioGeneration.created_at),
                )
                .group_by(StudioGeneration.user_id)
                .order_by(func.max(StudioGeneration.created_at).desc())
                .limit(limit)
            )
        ).all()
        for uid, cnt, last_at in rows:
            o = int(uid)
            owner_ids.append(o)
            details[o] = f"Генераций: {int(cnt or 0)}"
            if last_at:
                details[o] += f" · последняя {last_at.date().isoformat()}"
    elif segment == "owners_without_studio":
        studio_ids = await _owners_with_studio_ids(session)
        stmt = select(User.id).where(User.parent_user_id.is_(None))
        if studio_ids:
            stmt = stmt.where(~User.id.in_(studio_ids))
        rows = (await session.execute(stmt.order_by(User.created_at.desc()))).all()
        owner_ids = [int(r[0]) for r in rows][:limit]
    elif segment == "owners_with_chat":
        rows = (
            await session.execute(
                select(
                    Conversation.user_id,
                    func.count(Message.id),
                    func.max(Message.created_at),
                )
                .join(Message, Message.conversation_id == Conversation.id)
                .group_by(Conversation.user_id)
                .order_by(func.max(Message.created_at).desc())
                .limit(limit)
            )
        ).all()
        for uid, cnt, last_at in rows:
            o = int(uid)
            owner_ids.append(o)
            details[o] = f"Сообщений: {int(cnt or 0)}"
            if last_at:
                details[o] += f" · последнее {last_at.date().isoformat()}"
    elif segment == "registered_30d":
        rows = (
            await session.execute(
                select(User.id)
                .where(
                    User.parent_user_id.is_(None),
                    User.created_at >= since_30,
                )
                .order_by(User.created_at.desc())
                .limit(limit)
            )
        ).all()
        owner_ids = [int(r[0]) for r in rows]
    elif segment == "new_paid_active_30d":
        rows = (
            await session.execute(
                select(User.id)
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
                .order_by(User.created_at.desc())
                .limit(limit)
            )
        ).all()
        owner_ids = [int(r[0]) for r in rows]
    elif segment == "workspace_owners":
        rows = (
            await session.execute(
                select(User.id)
                .where(User.parent_user_id.is_(None))
                .order_by(User.created_at.desc())
                .limit(limit)
            )
        ).all()
        owner_ids = [int(r[0]) for r in rows]

    items = await _owners_by_ids(session, owner_ids, details=details, limit=limit)
    return {"segment": segment, "title": title, "total": len(items), "items": items}


async def _owners_with_studio_ids(session: AsyncSession) -> set[int]:
    rows = (await session.execute(select(StudioGeneration.user_id).distinct())).all()
    return {int(r[0]) for r in rows if r[0] is not None}


async def resolve_segment_owner_ids(session: AsyncSession, segment: str) -> list[int]:
    """Все owner_id сегмента (без лимита) — для email-рассылок."""
    if segment not in EMAIL_CAMPAIGN_SEGMENTS:
        raise ValueError(f"unknown or unsupported segment: {segment}")

    now = datetime.now(timezone.utc)
    since_7 = now - timedelta(days=7)
    since_30 = now - timedelta(days=30)

    if segment == "active_7d":
        return sorted(await _active_owner_ids(session, since_7), reverse=True)
    if segment == "active_30d":
        return sorted(await _active_owner_ids(session, since_30), reverse=True)
    if segment == "paid_active":
        rows = (
            await session.execute(
                select(User.id)
                .join(Subscription, Subscription.user_id == User.id)
                .where(
                    User.parent_user_id.is_(None),
                    Subscription.status == SubscriptionStatus.active,
                    or_(
                        Subscription.current_period_end.is_(None),
                        Subscription.current_period_end >= now,
                    ),
                )
                .order_by(User.created_at.desc())
            )
        ).all()
        return [int(r[0]) for r in rows]
    if segment == "trialing":
        rows = (
            await session.execute(
                select(User.id)
                .join(Subscription, Subscription.user_id == User.id)
                .where(
                    User.parent_user_id.is_(None),
                    Subscription.status == SubscriptionStatus.trialing,
                )
                .order_by(User.created_at.desc())
            )
        ).all()
        return [int(r[0]) for r in rows]
    if segment == "past_due":
        rows = (
            await session.execute(
                select(User.id)
                .join(Subscription, Subscription.user_id == User.id)
                .where(
                    User.parent_user_id.is_(None),
                    Subscription.status == SubscriptionStatus.past_due,
                )
                .order_by(User.created_at.desc())
            )
        ).all()
        return [int(r[0]) for r in rows]
    if segment == "paid_or_trialing":
        rows = (
            await session.execute(
                select(User.id)
                .join(Subscription, Subscription.user_id == User.id)
                .where(
                    User.parent_user_id.is_(None),
                    Subscription.status.in_(_PAID_SUBSCRIPTION_STATUSES),
                )
                .order_by(User.created_at.desc())
            )
        ).all()
        return [int(r[0]) for r in rows]
    if segment == "zombie":
        engaged = await _engaged_owner_ids(session)
        stmt = select(User.id).where(User.parent_user_id.is_(None))
        if engaged:
            stmt = stmt.where(~User.id.in_(engaged))
        rows = (await session.execute(stmt.order_by(User.created_at.desc()))).all()
        return [int(r[0]) for r in rows]
    if segment == "engaged_ever":
        return sorted(await _engaged_owner_ids(session), reverse=True)
    if segment == "yookassa_credits_buyers":
        rows = (
            await session.execute(
                select(_owner_id_expr().label("oid"))
                .select_from(UsageEvent)
                .join(User, User.id == UsageEvent.user_id)
                .where(UsageEvent.kind == "yookassa_credits_pack")
                .group_by(_owner_id_expr())
                .order_by(func.max(UsageEvent.created_at).desc())
            )
        ).all()
        return [int(r[0]) for r in rows]
    if segment == "owners_with_studio":
        rows = (
            await session.execute(
                select(StudioGeneration.user_id)
                .distinct()
                .order_by(StudioGeneration.user_id.desc())
            )
        ).all()
        return [int(r[0]) for r in rows]
    if segment == "owners_without_studio":
        studio_ids = await _owners_with_studio_ids(session)
        stmt = select(User.id).where(User.parent_user_id.is_(None))
        if studio_ids:
            stmt = stmt.where(~User.id.in_(studio_ids))
        rows = (await session.execute(stmt.order_by(User.created_at.desc()))).all()
        return [int(r[0]) for r in rows]
    if segment == "owners_with_chat":
        rows = (
            await session.execute(
                select(Conversation.user_id).distinct().order_by(Conversation.user_id.desc())
            )
        ).all()
        return [int(r[0]) for r in rows]
    if segment == "registered_30d":
        rows = (
            await session.execute(
                select(User.id)
                .where(
                    User.parent_user_id.is_(None),
                    User.created_at >= since_30,
                )
                .order_by(User.created_at.desc())
            )
        ).all()
        return [int(r[0]) for r in rows]
    if segment == "new_paid_active_30d":
        rows = (
            await session.execute(
                select(User.id)
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
                .order_by(User.created_at.desc())
            )
        ).all()
        return [int(r[0]) for r in rows]
    if segment == "referrals":
        rows = (
            await session.execute(
                select(User.id)
                .where(User.referred_by_user_id.isnot(None))
                .order_by(User.created_at.desc())
            )
        ).all()
        return [int(r[0]) for r in rows]
    if segment == "workspace_owners":
        rows = (
            await session.execute(
                select(User.id)
                .where(User.parent_user_id.is_(None))
                .order_by(User.created_at.desc())
            )
        ).all()
        return [int(r[0]) for r in rows]
    raise ValueError(f"unknown segment: {segment}")


async def count_email_eligible_recipients(
    session: AsyncSession,
    segment: str,
) -> dict[str, int]:
    """Сколько получателей в сегменте с учётом opt-out и неактивных."""
    owner_ids = await resolve_segment_owner_ids(session, segment)
    if not owner_ids:
        return {"segment_total": 0, "eligible": 0, "opted_out": 0, "inactive": 0}
    rows = (
        await session.execute(
            select(User.id, User.is_active, User.email_marketing_opt_out).where(
                User.id.in_(owner_ids)
            )
        )
    ).all()
    by_id = {int(r[0]): (bool(r[1]), bool(r[2])) for r in rows}
    opted_out = inactive = 0
    eligible = 0
    for oid in owner_ids:
        info = by_id.get(oid)
        if not info:
            continue
        is_active, opt_out = info
        if opt_out:
            opted_out += 1
        elif not is_active:
            inactive += 1
        else:
            eligible += 1
    return {
        "segment_total": len(owner_ids),
        "eligible": eligible,
        "opted_out": opted_out,
        "inactive": inactive,
    }

