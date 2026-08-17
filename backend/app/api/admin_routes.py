from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_platform_admin
from app.auth.passwords import hash_password
from app.db.models import (
    Conversation,
    CreditAccount,
    StudioGeneration,
    Subscription,
    SubscriptionStatus,
    UsageEvent,
    User,
    UserStudioModel,
)
from app.db.session import get_session
from app.schemas import (
    AdminCreditsIn,
    AdminCreditsOut,
    AdminCreditHistoryItemOut,
    AdminCreditHistoryPageOut,
    AdminDemoGenerationsIn,
    AdminDemoGenerationsOut,
    AdminPartnerAttributionIn,
    AdminPartnerAttributionOut,
    AdminPartnerBackfillOut,
    AdminPasswordResetIn,
    AdminSegmentOut,
    AdminStatsOut,
    AdminSubscriptionPatchIn,
    AdminUserDetailOut,
    AdminUserListOut,
    AdminUserPatchIn,
    AdminUserRow,
)
from app.services.admin_analytics import build_admin_dashboard
from app.services.funnel_analytics import build_activation_funnel
from app.services.admin_segments import VALID_ADMIN_SEGMENTS, list_admin_segment
from app.services.billing_plan import normalize_billing_plan
from app.services.credits import admin_adjust_credits
from app.services.demo_generations import admin_adjust_demo_generations
from app.services.workspace import workspace_owner_id

router = APIRouter(tags=["admin"])


async def _owner_studio_counts(
    session: AsyncSession, owner_ids: list[int]
) -> tuple[dict[int, int], dict[int, int]]:
    if not owner_ids:
        return {}, {}
    models: dict[int, int] = {}
    gens: dict[int, int] = {}
    for uid, n in (
        await session.execute(
            select(UserStudioModel.user_id, func.count(UserStudioModel.id))
            .where(UserStudioModel.user_id.in_(owner_ids))
            .group_by(UserStudioModel.user_id)
        )
    ).all():
        models[int(uid)] = int(n or 0)
    for uid, n in (
        await session.execute(
            select(StudioGeneration.user_id, func.count(StudioGeneration.id))
            .where(StudioGeneration.user_id.in_(owner_ids))
            .group_by(StudioGeneration.user_id)
        )
    ).all():
        gens[int(uid)] = int(n or 0)
    return models, gens


def _admin_users_base_stmt(*, q: str | None, partners_only: bool):
    stmt = select(User).options(selectinload(User.parent))
    if q and str(q).strip():
        pat = f"%{str(q).strip()}%"
        stmt = stmt.where(User.email.ilike(pat))
    if partners_only:
        stmt = stmt.where(User.is_partner.is_(True), User.parent_user_id.is_(None))
    return stmt


async def _admin_users_total(
    session: AsyncSession, *, q: str | None, partners_only: bool
) -> int:
    count_stmt = select(func.count()).select_from(User)
    if q and str(q).strip():
        pat = f"%{str(q).strip()}%"
        count_stmt = count_stmt.where(User.email.ilike(pat))
    if partners_only:
        count_stmt = count_stmt.where(
            User.is_partner.is_(True), User.parent_user_id.is_(None)
        )
    return int(await session.scalar(count_stmt) or 0)


def _owner_subscription_tuple(
    sub: Subscription | None,
) -> tuple[str, str, str | None, datetime | None]:
    st = sub.status.value if sub else SubscriptionStatus.none.value
    bp = (sub.billing_plan if sub else None) or "credits"
    tier = sub.plan_tier if sub else None
    pend = sub.current_period_end if sub else None
    return st, bp, tier, pend


async def _user_row(
    session: AsyncSession,
    u: User,
    *,
    owner_bal: dict[int, int],
    owner_demo: dict[int, int],
    owner_sub: dict[int, tuple[str, str, str | None, datetime | None]],
    owner_models: dict[int, int],
    owner_gens: dict[int, int],
) -> AdminUserRow:
    oid = workspace_owner_id(u)
    if oid not in owner_bal or oid not in owner_demo:
        acc = await session.get(CreditAccount, oid)
        owner_bal[oid] = acc.balance if acc else 0
        owner_demo[oid] = int(acc.demo_generations_remaining) if acc else 0
    if oid not in owner_sub:
        ow_stmt = (
            select(User)
            .where(User.id == oid)
            .options(selectinload(User.subscription))
        )
        ow = (await session.execute(ow_stmt)).scalar_one_or_none()
        owner_sub[oid] = _owner_subscription_tuple(ow.subscription if ow else None)
    st, bp, tier, pend = owner_sub[oid]
    return AdminUserRow(
        id=u.id,
        email=u.email,
        created_at=u.created_at,
        is_active=u.is_active,
        is_platform_admin=bool(u.is_platform_admin),
        is_partner=bool(getattr(u, "is_partner", False)),
        partner_slug=(getattr(u, "partner_slug", None) or None),
        parent_user_id=u.parent_user_id,
        parent_email=u.parent.email if u.parent else None,
        member_login=u.member_login,
        subscription_status=st,
        billing_plan=bp,
        plan_tier=tier,
        subscription_period_end=pend,
        credits_balance=owner_bal[oid],
        demo_generations_remaining=owner_demo[oid],
        studio_models_count=owner_models.get(oid, 0),
        studio_generations_count=owner_gens.get(oid, 0),
    )


@router.get("/admin/stats", response_model=AdminStatsOut)
async def admin_stats(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
    chart_days: int = Query(default=30, ge=7, le=90),
) -> AdminStatsOut:
    data = await build_admin_dashboard(session, chart_days=chart_days)
    data["activation_funnel"] = await build_activation_funnel(session, days=chart_days)
    return AdminStatsOut(**data)


@router.get("/admin/stats/segment", response_model=AdminSegmentOut)
async def admin_stats_segment(
    segment: str = Query(..., min_length=1, max_length=64),
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
    limit: int = Query(default=200, ge=1, le=500),
) -> AdminSegmentOut:
    key = segment.strip().lower()
    if key not in VALID_ADMIN_SEGMENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Неизвестный сегмент. Доступны: {', '.join(sorted(VALID_ADMIN_SEGMENTS))}",
        )
    try:
        data = await list_admin_segment(session, key, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return AdminSegmentOut(**data)


@router.get("/admin/users", response_model=AdminUserListOut)
async def admin_list_users(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
    q: str | None = Query(default=None, max_length=120),
    partners_only: bool = Query(default=False),
) -> AdminUserListOut:
    page_limit = min(200, max(1, limit))
    page_skip = max(0, skip)
    stmt = (
        _admin_users_base_stmt(q=q, partners_only=partners_only)
        .order_by(User.id.desc())
        .offset(page_skip)
        .limit(page_limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    total = await _admin_users_total(session, q=q, partners_only=partners_only)

    owner_bal: dict[int, int] = {}
    owner_demo: dict[int, int] = {}
    owner_sub: dict[int, tuple[str, str, str | None, datetime | None]] = {}
    owner_ids = list({workspace_owner_id(u) for u in rows})
    owner_models, owner_gens = await _owner_studio_counts(session, owner_ids)
    out: list[AdminUserRow] = []
    for u in rows:
        out.append(
            await _user_row(
                session,
                u,
                owner_bal=owner_bal,
                owner_demo=owner_demo,
                owner_sub=owner_sub,
                owner_models=owner_models,
                owner_gens=owner_gens,
            )
        )
    return AdminUserListOut(
        items=out,
        total=total,
        skip=page_skip,
        limit=page_limit,
    )


@router.get("/admin/users/{user_id}", response_model=AdminUserDetailOut)
async def admin_get_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
) -> AdminUserDetailOut:
    stmt = select(User).where(User.id == user_id).options(selectinload(User.parent))
    u = (await session.execute(stmt)).scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    oid = workspace_owner_id(u)
    owner_models, owner_gens = await _owner_studio_counts(session, [oid])
    base = await _user_row(
        session,
        u,
        owner_bal={},
        owner_demo={},
        owner_sub={},
        owner_models=owner_models,
        owner_gens=owner_gens,
    )
    invited_users_count = int(
        await session.scalar(
            select(func.count(User.id)).where(User.referred_by_user_id == oid)
        )
        or 0
    )
    conversations_count = int(
        await session.scalar(
            select(func.count(Conversation.id)).where(Conversation.user_id == oid)
        )
        or 0
    )
    workspace_members_count = int(
        await session.scalar(
            select(func.count(User.id)).where(User.parent_user_id == oid)
        )
        or 0
    )
    referred_by_email = None
    if u.referred_by_user_id:
        ref = await session.get(User, u.referred_by_user_id)
        referred_by_email = ref.email if ref else None
    return AdminUserDetailOut(
        **base.model_dump(),
        invited_users_count=invited_users_count,
        referred_by_email=referred_by_email,
        conversations_count=conversations_count,
        workspace_members_count=workspace_members_count,
    )


@router.patch("/admin/users/{user_id}", response_model=AdminUserRow)
async def admin_patch_user(
    user_id: int,
    body: AdminUserPatchIn,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
) -> AdminUserRow:
    stmt = select(User).where(User.id == user_id).options(selectinload(User.parent))
    u = (await session.execute(stmt)).scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if body.is_platform_admin is not None:
        if u.parent_user_id is not None:
            raise HTTPException(
                status_code=400,
                detail="Флаг админа только у аккаунта владельца (без parent_user_id)",
            )
        u.is_platform_admin = body.is_platform_admin
    if body.is_active is not None:
        u.is_active = body.is_active
    if body.is_partner is not None:
        if u.parent_user_id is not None:
            raise HTTPException(
                status_code=400,
                detail="Партнёрский статус только у аккаунта владельца",
            )
        u.is_partner = body.is_partner
        if body.is_partner:
            from app.services.partner import ensure_partner_slug

            await ensure_partner_slug(session, u)
    if body.partner_slug is not None:
        if u.parent_user_id is not None:
            raise HTTPException(
                status_code=400,
                detail="Партнёрский slug только у аккаунта владельца",
            )
        is_partner = body.is_partner if body.is_partner is not None else bool(u.is_partner)
        if not is_partner:
            raise HTTPException(
                status_code=400,
                detail="Партнёрский slug задаётся только партнёрам",
            )
        dup_id = await session.scalar(
            select(User.id).where(
                User.partner_slug == body.partner_slug,
                User.id != u.id,
            )
        )
        if dup_id:
            raise HTTPException(
                status_code=409,
                detail=f"Slug «{body.partner_slug}» уже занят",
            )
        u.partner_slug = body.partner_slug
    await session.commit()
    await session.refresh(u)
    oid = workspace_owner_id(u)
    owner_models, owner_gens = await _owner_studio_counts(session, [oid])
    return await _user_row(
        session,
        u,
        owner_bal={},
        owner_demo={},
        owner_sub={},
        owner_models=owner_models,
        owner_gens=owner_gens,
    )


@router.post("/admin/users/{user_id}/password")
async def admin_user_password(
    user_id: int,
    body: AdminPasswordResetIn,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
) -> dict[str, bool]:
    u = await session.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    u.hashed_password = hash_password(body.password)
    await session.commit()
    return {"ok": True}


@router.post("/admin/users/{user_id}/credits", response_model=AdminCreditsOut)
async def admin_user_credits(
    user_id: int,
    body: AdminCreditsIn,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_platform_admin),
) -> AdminCreditsOut:
    target = await session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    billing_id = workspace_owner_id(target)
    try:
        new_bal = await admin_adjust_credits(
            session,
            billing_user_id=billing_id,
            delta=body.delta,
            admin_user_id=admin.id,
            note=body.note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await session.commit()
    return AdminCreditsOut(new_balance=new_bal, billing_user_id=billing_id)


@router.get("/admin/users/{user_id}/credit-history", response_model=AdminCreditHistoryPageOut)
async def admin_user_credit_history(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
) -> AdminCreditHistoryPageOut:
    target = await session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    billing_id = workspace_owner_id(target)
    off = max(0, skip)
    lim = min(200, max(1, limit))
    stmt = (
        select(UsageEvent)
        .where(UsageEvent.user_id == billing_id)
        .order_by(UsageEvent.id.desc())
        .offset(off)
        .limit(lim + 1)
    )
    rows = (await session.execute(stmt)).scalars().all()
    has_more = len(rows) > lim
    rows = rows[:lim]
    return AdminCreditHistoryPageOut(
        billing_user_id=billing_id,
        items=[AdminCreditHistoryItemOut.model_validate(r) for r in rows],
        has_more=has_more,
    )


@router.post("/admin/users/{user_id}/demo-generations", response_model=AdminDemoGenerationsOut)
async def admin_user_demo_generations(
    user_id: int,
    body: AdminDemoGenerationsIn,
    session: AsyncSession = Depends(get_session),
    admin: User = Depends(get_platform_admin),
) -> AdminDemoGenerationsOut:
    target = await session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    billing_id = workspace_owner_id(target)
    try:
        new_demo = await admin_adjust_demo_generations(
            session,
            billing_user_id=billing_id,
            delta=body.delta,
            admin_user_id=admin.id,
            note=body.note,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await session.commit()
    return AdminDemoGenerationsOut(
        demo_generations_remaining=new_demo,
        billing_user_id=billing_id,
    )


@router.patch("/admin/users/{user_id}/subscription")
async def admin_user_subscription(
    user_id: int,
    body: AdminSubscriptionPatchIn,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
) -> dict:
    target = await session.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    billing_id = workspace_owner_id(target)
    stmt = select(Subscription).where(Subscription.user_id == billing_id)
    sub = (await session.execute(stmt)).scalar_one_or_none()
    if not sub:
        sub = Subscription(user_id=billing_id, status=SubscriptionStatus.none)
        session.add(sub)
        await session.flush()
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=400, detail="Нет полей для обновления")
    if "status" in patch:
        try:
            sub.status = SubscriptionStatus(patch["status"])
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail="Недопустимый status (none|incomplete|trialing|active|past_due|canceled|unpaid)",
            ) from e
    if "plan_tier" in patch:
        from app.services.plan_catalog import normalize_plan_tier

        raw = (body.plan_tier or "").strip().lower() or None
        sub.plan_tier = normalize_plan_tier(raw) if raw else None
    if "current_period_end" in patch:
        sub.current_period_end = body.current_period_end
    if "billing_plan" in patch:
        sub.billing_plan = normalize_billing_plan(body.billing_plan)
    await session.commit()
    return {"ok": True}


@router.post(
    "/admin/users/{user_id}/partner-attribution",
    response_model=AdminPartnerAttributionOut,
)
async def admin_user_partner_attribution(
    user_id: int,
    body: AdminPartnerAttributionIn,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
) -> AdminPartnerAttributionOut:
    from app.services.partner import (
        assign_user_to_partner_retroactive,
        backfill_partner_commissions_for_user,
    )

    u = await session.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    oid = workspace_owner_id(u)
    owner = await session.get(User, oid)
    if owner is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    try:
        partner = await assign_user_to_partner_retroactive(
            session,
            user=owner,
            partner_slug=body.partner_slug,
            source_tag=body.source_tag,
            force=body.force,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    backfill_stats = {"created": 0, "skipped": 0, "events": 0}
    if body.backfill_commissions:
        backfill_stats = await backfill_partner_commissions_for_user(
            session, referred_owner_id=oid
        )

    await session.commit()
    slug = (partner.partner_slug or body.partner_slug).strip().lower()
    return AdminPartnerAttributionOut(
        user_id=oid,
        partner_user_id=partner.id,
        partner_slug=slug,
        referred_by_email=partner.email,
        commissions_created=int(backfill_stats.get("created") or 0),
        commissions_skipped=int(backfill_stats.get("skipped") or 0),
        payment_events_scanned=int(backfill_stats.get("events") or 0),
    )


@router.post(
    "/admin/partners/{partner_id}/backfill-commissions",
    response_model=AdminPartnerBackfillOut,
)
async def admin_partner_backfill_commissions(
    partner_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
) -> AdminPartnerBackfillOut:
    from app.services.partner import backfill_partner_commissions_for_user

    partner = await session.get(User, partner_id)
    if partner is None or not getattr(partner, "is_partner", False):
        raise HTTPException(status_code=404, detail="Партнёр не найден")

    referred_ids = (
        await session.execute(
            select(User.id).where(User.referred_by_user_id == partner_id)
        )
    ).scalars().all()

    total_created = 0
    total_skipped = 0
    for rid in referred_ids:
        stats = await backfill_partner_commissions_for_user(
            session, referred_owner_id=int(rid)
        )
        total_created += int(stats.get("created") or 0)
        total_skipped += int(stats.get("skipped") or 0)

    await session.commit()
    return AdminPartnerBackfillOut(
        partner_user_id=partner_id,
        users_processed=len(referred_ids),
        commissions_created=total_created,
        commissions_skipped=total_skipped,
    )
