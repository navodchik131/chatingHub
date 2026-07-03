"""Управление участниками рабочего пространства (только владелец)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.passwords import hash_password
from app.db.models import ChatterSnippet, Subscription, UsageEvent, User
from app.db.session import get_session
from app.schemas import (
    ChatterSnippetIn,
    ChatterSnippetOut,
    ChatterSnippetPatchIn,
    ChatterStatsSummaryOut,
    CreditHistoryItemOut,
    CreditHistoryPageOut,
    WorkspaceMemberCreateIn,
    WorkspaceMemberOut,
    WorkspaceMemberPatchIn,
)
from app.services.chatter_stats import aggregate_chatter_stats_summary
from app.services.workspace import (
    DEFAULT_MEMBER_PERMISSIONS,
    PERM_CHAT,
    assert_permission,
    is_workspace_owner,
    normalize_member_login,
    synthetic_member_email,
)
from app.services.workspace_model_access import (
    load_member_studio_model_ids,
    replace_member_studio_models,
)
from app.services.tribute_member_share import resolve_member_tribute_share_percent
from app.services.workspace import workspace_owner_id

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.get("/snippets", response_model=list[ChatterSnippetOut])
async def list_chatter_snippets(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[ChatterSnippetOut]:
    assert_permission(user, PERM_CHAT)
    oid = workspace_owner_id(user)
    rows = list(
        (
            await session.scalars(
                select(ChatterSnippet)
                .where(ChatterSnippet.user_id == oid)
                .order_by(
                    ChatterSnippet.sort_order.asc(),
                    ChatterSnippet.id.asc(),
                )
            )
        ).all()
    )
    return [ChatterSnippetOut.model_validate(r) for r in rows]


@router.post("/snippets", response_model=ChatterSnippetOut)
async def create_chatter_snippet(
    body: ChatterSnippetIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ChatterSnippetOut:
    assert_permission(user, PERM_CHAT)
    oid = workspace_owner_id(user)
    row = ChatterSnippet(
        user_id=oid,
        title=body.title.strip(),
        body=body.body.strip(),
        lang=(body.lang or "").strip() or None,
        sort_order=int(body.sort_order or 0),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return ChatterSnippetOut.model_validate(row)


@router.patch("/snippets/{snippet_id}", response_model=ChatterSnippetOut)
async def patch_chatter_snippet(
    snippet_id: int,
    body: ChatterSnippetPatchIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ChatterSnippetOut:
    assert_permission(user, PERM_CHAT)
    oid = workspace_owner_id(user)
    row = await session.get(ChatterSnippet, snippet_id)
    if not row or row.user_id != oid:
        raise HTTPException(status_code=404, detail="Snippet not found")
    if body.title is not None:
        row.title = body.title.strip()
    if body.body is not None:
        row.body = body.body.strip()
    if body.lang is not None:
        row.lang = body.lang.strip() or None
    if body.sort_order is not None:
        row.sort_order = int(body.sort_order)
    await session.commit()
    await session.refresh(row)
    return ChatterSnippetOut.model_validate(row)


@router.delete("/snippets/{snippet_id}")
async def delete_chatter_snippet(
    snippet_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    assert_permission(user, PERM_CHAT)
    oid = workspace_owner_id(user)
    row = await session.get(ChatterSnippet, snippet_id)
    if not row or row.user_id != oid:
        raise HTTPException(status_code=404, detail="Snippet not found")
    await session.delete(row)
    await session.commit()
    return {"ok": True}


@router.get("/chatter-stats/summary", response_model=ChatterStatsSummaryOut)
async def chatter_stats_summary(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ChatterStatsSummaryOut:
    assert_permission(user, PERM_CHAT)
    today = date.today()
    if from_date is None and to_date is None:
        from_date = today.replace(day=1)
        to_date = today
    elif from_date is None:
        from_date = to_date or today
    elif to_date is None:
        to_date = today
    data = await aggregate_chatter_stats_summary(
        session,
        viewer=user,
        from_date=from_date,
        to_date=to_date,
    )
    return ChatterStatsSummaryOut.model_validate(data)


@router.get("/credit-history", response_model=CreditHistoryPageOut)
async def credit_history(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
    limit: int = 40,
    skip: int = 0,
) -> CreditHistoryPageOut:
    _require_workspace_owner(user)
    lim = min(100, max(1, limit))
    off = max(0, skip)
    stmt = (
        select(UsageEvent)
        .where(UsageEvent.user_id == user.id)
        .order_by(UsageEvent.id.desc())
        .offset(off)
        .limit(lim + 1)
    )
    rows = (await session.execute(stmt)).scalars().all()
    has_more = len(rows) > lim
    rows = rows[:lim]
    items = [CreditHistoryItemOut.model_validate(r) for r in rows]
    return CreditHistoryPageOut(items=items, has_more=has_more)


def _require_workspace_owner(user: User) -> None:
    if not is_workspace_owner(user):
        raise HTTPException(
            status_code=403,
            detail="Управление командой доступно только владельцу аккаунта",
        )


async def _member_out(session: AsyncSession, m: User) -> WorkspaceMemberOut:
    model_ids = await load_member_studio_model_ids(session, m.id)
    return WorkspaceMemberOut(
        id=m.id,
        member_login=m.member_login or "",
        permissions_mask=m.permissions_mask,
        is_active=m.is_active,
        allowed_studio_model_ids=model_ids,
        tribute_share_percent=resolve_member_tribute_share_percent(m),
    )


@router.get("/members", response_model=list[WorkspaceMemberOut])
async def list_workspace_members(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[WorkspaceMemberOut]:
    _require_workspace_owner(user)
    stmt = (
        select(User)
        .where(User.parent_user_id == user.id)
        .order_by(User.id.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    out: list[WorkspaceMemberOut] = []
    for m in rows:
        out.append(await _member_out(session, m))
    return out


@router.post("/members", response_model=WorkspaceMemberOut)
async def create_workspace_member(
    body: WorkspaceMemberCreateIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> WorkspaceMemberOut:
    _require_workspace_owner(user)
    sub = await session.scalar(select(Subscription).where(Subscription.user_id == user.id))
    from app.services.plan_entitlements import assert_can_add_workspace_member

    await assert_can_add_workspace_member(session, user, sub)
    login = normalize_member_login(body.member_login)
    email = synthetic_member_email(user.id, login)
    dup = await session.scalar(select(User.id).where(User.email == email))
    if dup:
        raise HTTPException(status_code=400, detail="Такой логин уже занят в пространстве")
    dup2 = await session.scalar(
        select(User.id).where(
            User.parent_user_id == user.id,
            User.member_login == login,
        )
    )
    if dup2:
        raise HTTPException(status_code=400, detail="Такой логин уже занят в пространстве")
    mask = (
        body.permissions_mask
        if body.permissions_mask is not None
        else DEFAULT_MEMBER_PERMISSIONS
    )
    member = User(
        email=email,
        hashed_password=hash_password(body.password),
        parent_user_id=user.id,
        member_login=login,
        permissions_mask=int(mask),
        is_active=True,
        tribute_share_percent=body.tribute_share_percent,
    )
    session.add(member)
    await session.flush()
    await replace_member_studio_models(
        session, user.id, member, body.allowed_studio_model_ids
    )
    await session.commit()
    await session.refresh(member)
    return await _member_out(session, member)


@router.patch("/members/{member_id}", response_model=WorkspaceMemberOut)
async def patch_workspace_member(
    member_id: int,
    body: WorkspaceMemberPatchIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> WorkspaceMemberOut:
    _require_workspace_owner(user)
    m = await session.get(User, member_id)
    if not m or m.parent_user_id != user.id:
        raise HTTPException(status_code=404, detail="Участник не найден")
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Нет полей для обновления")
    if "permissions_mask" in data and data["permissions_mask"] is not None:
        m.permissions_mask = int(data["permissions_mask"])
    if "password" in data and data["password"]:
        m.hashed_password = hash_password(data["password"])
    if "is_active" in data and data["is_active"] is not None:
        m.is_active = bool(data["is_active"])
    if "allowed_studio_model_ids" in data:
        await replace_member_studio_models(
            session,
            user.id,
            m,
            data["allowed_studio_model_ids"] or [],
        )
    if "tribute_share_percent" in data:
        m.tribute_share_percent = data["tribute_share_percent"]
    await session.commit()
    await session.refresh(m)
    return await _member_out(session, m)


@router.delete("/members/{member_id}")
async def delete_workspace_member(
    member_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    _require_workspace_owner(user)
    if member_id == user.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить самого себя")
    m = await session.get(User, member_id)
    if not m or m.parent_user_id != user.id:
        raise HTTPException(status_code=404, detail="Участник не найден")
    await session.delete(m)
    await session.commit()
    return {"ok": True}
