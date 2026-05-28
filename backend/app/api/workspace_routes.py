"""Управление участниками рабочего пространства (только владелец)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.passwords import hash_password
from app.db.models import Subscription, UsageEvent, User
from app.db.session import get_session
from app.schemas import (
    CreditHistoryItemOut,
    CreditHistoryPageOut,
    WorkspaceMemberCreateIn,
    WorkspaceMemberOut,
    WorkspaceMemberPatchIn,
)
from app.services.workspace import (
    DEFAULT_MEMBER_PERMISSIONS,
    is_workspace_owner,
    normalize_member_login,
    synthetic_member_email,
)
from app.services.workspace_model_access import (
    load_member_studio_model_ids,
    replace_member_studio_models,
)

router = APIRouter(prefix="/workspace", tags=["workspace"])


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
