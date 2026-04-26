"""Рабочее пространство: владелец + участники с правами (общий биллинг и данные)."""

from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import User

# Биты прав (можно комбинировать через |)
PERM_CHAT = 1
PERM_STUDIO_GENERATE = 2
PERM_STUDIO_MODELS = 4
PERM_INTEGRATIONS = 8
PERM_BILLING = 16
PERM_MANAGE_MEMBERS = 32

DEFAULT_MEMBER_PERMISSIONS = PERM_CHAT | PERM_STUDIO_GENERATE | PERM_STUDIO_MODELS

_MEMBER_LOGIN_RE = re.compile(r"^[a-z0-9_]{3,32}$")


def workspace_owner_id(user: User) -> int:
    return user.parent_user_id if user.parent_user_id is not None else user.id


def is_workspace_owner(user: User) -> bool:
    return user.parent_user_id is None


def has_permission(user: User, perm: int) -> bool:
    if is_workspace_owner(user):
        return True
    return (user.permissions_mask & perm) == perm


def has_any_studio_access(user: User) -> bool:
    if is_workspace_owner(user):
        return True
    m = user.permissions_mask
    return bool(m & (PERM_STUDIO_GENERATE | PERM_STUDIO_MODELS))


def assert_permission(user: User, perm: int) -> None:
    if not has_permission(user, perm):
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав для этого действия",
        )


def normalize_member_login(raw: str) -> str:
    s = (raw or "").strip().lower()
    if not _MEMBER_LOGIN_RE.match(s):
        raise HTTPException(
            status_code=400,
            detail="Логин сотрудника: 3–32 символа, латиница, цифры и подчёркивание",
        )
    return s


def synthetic_member_email(parent_id: int, login: str) -> str:
    return f"{login}.w{parent_id}@workspace.local"


async def resolve_billing_user(session: AsyncSession, user: User) -> User:
    """Пользователь, у которого списываются кредиты и подписка (владелец пространства)."""
    oid = workspace_owner_id(user)
    if oid == user.id:
        return user
    stmt = (
        select(User)
        .where(User.id == oid, User.is_active.is_(True))
        .options(
            selectinload(User.subscription),
            selectinload(User.credit_account),
        )
    )
    owner = (await session.execute(stmt)).scalar_one_or_none()
    if not owner:
        raise HTTPException(status_code=403, detail="Владелец пространства недоступен")
    return owner
