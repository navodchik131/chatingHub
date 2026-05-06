from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_platform_admin
from app.db.models import (
    CreditAccount,
    StudioGeneration,
    Subscription,
    SubscriptionStatus,
    UsageEvent,
    User,
)
from app.db.session import get_session
from app.schemas import (
    AdminCreditsIn,
    AdminCreditsOut,
    AdminStatsOut,
    AdminSubscriptionPatchIn,
    AdminUserPatchIn,
    AdminUserRow,
)
from app.services.billing_plan import normalize_billing_plan
from app.services.credits import admin_adjust_credits
from app.services.workspace import workspace_owner_id

router = APIRouter(tags=["admin"])


@router.get("/admin/stats", response_model=AdminStatsOut)
async def admin_stats(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
) -> AdminStatsOut:
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

    kind_rows = (
        await session.execute(
            select(UsageEvent.kind, func.count(UsageEvent.id)).group_by(UsageEvent.kind)
        )
    ).all()
    by_kind: dict[str, int] = {str(k or ""): int(c) for k, c in kind_rows}

    return AdminStatsOut(
        total_users=total_users,
        workspace_owners=owners,
        workspace_members=members,
        total_credits_balance=total_credits,
        studio_generations_total=gen_total,
        usage_by_kind=by_kind,
    )


@router.get("/admin/users", response_model=list[AdminUserRow])
async def admin_list_users(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
    skip: int = 0,
    limit: int = 50,
    q: str | None = None,
) -> list[AdminUserRow]:
    stmt = (
        select(User)
        .options(selectinload(User.parent))
        .order_by(User.id.desc())
        .offset(max(0, skip))
        .limit(min(200, max(1, limit)))
    )
    if q and str(q).strip():
        pat = f"%{str(q).strip()}%"
        stmt = stmt.where(User.email.ilike(pat))
    rows = (await session.execute(stmt)).scalars().all()

    owner_bal: dict[int, int] = {}
    owner_sub: dict[int, tuple[str, str, datetime | None]] = {}
    out: list[AdminUserRow] = []
    for u in rows:
        oid = workspace_owner_id(u)
        if oid not in owner_bal:
            acc = await session.get(CreditAccount, oid)
            owner_bal[oid] = acc.balance if acc else 0
        if oid not in owner_sub:
            ow_stmt = (
                select(User)
                .where(User.id == oid)
                .options(selectinload(User.subscription))
            )
            ow = (await session.execute(ow_stmt)).scalar_one_or_none()
            s = ow.subscription if ow else None
            st = s.status.value if s else SubscriptionStatus.none.value
            bp = (s.billing_plan if s else None) or "managed"
            pend = s.current_period_end if s else None
            owner_sub[oid] = (st, bp, pend)
        st, bp, pend = owner_sub[oid]
        out.append(
            AdminUserRow(
                id=u.id,
                email=u.email,
                created_at=u.created_at,
                is_active=u.is_active,
                is_platform_admin=bool(u.is_platform_admin),
                parent_user_id=u.parent_user_id,
                parent_email=u.parent.email if u.parent else None,
                member_login=u.member_login,
                subscription_status=st,
                billing_plan=bp,
                subscription_period_end=pend,
                credits_balance=owner_bal[oid],
            )
        )
    return out


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
    await session.commit()
    await session.refresh(u)
    par = await session.get(User, u.parent_user_id) if u.parent_user_id else None
    parent_email = par.email if par else None
    oid = workspace_owner_id(u)
    acc = await session.get(CreditAccount, oid)
    bal = acc.balance if acc else 0
    ow_row = await session.get(User, oid, options=(selectinload(User.subscription),))
    sub = ow_row.subscription if ow_row else None
    return AdminUserRow(
        id=u.id,
        email=u.email,
        created_at=u.created_at,
        is_active=u.is_active,
        is_platform_admin=bool(u.is_platform_admin),
        parent_user_id=u.parent_user_id,
        parent_email=parent_email,
        member_login=u.member_login,
        subscription_status=sub.status.value
        if sub
        else SubscriptionStatus.none.value,
        billing_plan=(sub.billing_plan if sub else None) or "managed",
        subscription_period_end=sub.current_period_end if sub else None,
        credits_balance=bal,
    )


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
        sub.plan_tier = (body.plan_tier or "")[:64] or None
    if "current_period_end" in patch:
        sub.current_period_end = body.current_period_end
    if "billing_plan" in patch:
        sub.billing_plan = normalize_billing_plan(body.billing_plan)
    await session.commit()
    return {"ok": True}
