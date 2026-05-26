"""Доступ участников workspace к моделям студии и чатам (ручной allowlist)."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import delete, false, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Conversation,
    User,
    UserStudioModel,
    WorkspaceMemberStudioModel,
)
from app.db.repo import get_conversation
from app.services.workspace import is_workspace_owner, workspace_owner_id


async def member_allowed_studio_model_ids(
    session: AsyncSession, user: User
) -> set[int] | None:
    """None — владелец (без фильтра); иначе множество id моделей участника."""
    if is_workspace_owner(user):
        return None
    stmt = select(WorkspaceMemberStudioModel.studio_model_id).where(
        WorkspaceMemberStudioModel.member_user_id == user.id
    )
    rows = (await session.execute(stmt)).scalars().all()
    return set(rows)


def apply_studio_model_id_filter(stmt, column, allowed: set[int] | None):
    if allowed is None:
        return stmt
    if not allowed:
        return stmt.where(false())
    return stmt.where(column.in_(allowed))


async def load_member_studio_model_ids(
    session: AsyncSession, member_user_id: int
) -> list[int]:
    stmt = (
        select(WorkspaceMemberStudioModel.studio_model_id)
        .where(WorkspaceMemberStudioModel.member_user_id == member_user_id)
        .order_by(WorkspaceMemberStudioModel.studio_model_id.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def replace_member_studio_models(
    session: AsyncSession,
    owner_id: int,
    member: User,
    model_ids: list[int],
) -> None:
    if member.parent_user_id != owner_id:
        raise HTTPException(status_code=404, detail="Участник не найден")
    unique = sorted({int(x) for x in model_ids if int(x) > 0})
    if unique:
        stmt = select(UserStudioModel.id).where(
            UserStudioModel.user_id == owner_id,
            UserStudioModel.id.in_(unique),
        )
        found = set((await session.execute(stmt)).scalars().all())
        missing = set(unique) - found
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Неизвестные модели: {', '.join(str(i) for i in sorted(missing))}",
            )
    await session.execute(
        delete(WorkspaceMemberStudioModel).where(
            WorkspaceMemberStudioModel.member_user_id == member.id
        )
    )
    for mid in unique:
        session.add(
            WorkspaceMemberStudioModel(
                member_user_id=member.id,
                studio_model_id=mid,
            )
        )


async def require_studio_model_access(
    session: AsyncSession,
    user: User,
    model_id: int,
    *,
    load_images: bool = False,
) -> UserStudioModel:
    oid = workspace_owner_id(user)
    stmt = select(UserStudioModel).where(
        UserStudioModel.id == model_id,
        UserStudioModel.user_id == oid,
    )
    if load_images:
        stmt = stmt.options(selectinload(UserStudioModel.images))
    m = (await session.execute(stmt)).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Модель не найдена")
    allowed = await member_allowed_studio_model_ids(session, user)
    if allowed is not None and model_id not in allowed:
        raise HTTPException(status_code=403, detail="Нет доступа к этой модели")
    return m


def require_workspace_owner(user: User) -> None:
    if not is_workspace_owner(user):
        raise HTTPException(
            status_code=403,
            detail="Действие доступно только владельцу аккаунта",
        )


async def assert_studio_generation_access(
    session: AsyncSession, user: User, studio_model_id: int | None
) -> None:
    allowed = await member_allowed_studio_model_ids(session, user)
    if allowed is None:
        return
    if studio_model_id is None or studio_model_id not in allowed:
        raise HTTPException(status_code=403, detail="Нет доступа к этой генерации")


async def assert_motion_render_access(
    session: AsyncSession, user: User, studio_model_id: int | None
) -> None:
    await assert_studio_generation_access(session, user, studio_model_id)


async def require_conversation_chat_access(
    session: AsyncSession,
    user: User,
    conv_id: int,
    owner_id: int,
) -> Conversation:
    conv = await get_conversation(session, conv_id, owner_id)
    if not conv:
        raise HTTPException(status_code=404, detail="conversation not found")
    allowed = await member_allowed_studio_model_ids(session, user)
    if allowed is not None:
        mid = conv.studio_model_id
        if mid is None or mid not in allowed:
            raise HTTPException(status_code=403, detail="Нет доступа к этому диалогу")
    return conv


async def filter_conversations_for_member(
    session: AsyncSession, user: User, convs: list[Conversation]
) -> list[Conversation]:
    allowed = await member_allowed_studio_model_ids(session, user)
    if allowed is None:
        return convs
    return [
        c
        for c in convs
        if c.studio_model_id is not None and c.studio_model_id in allowed
    ]


async def validate_owner_studio_model_id(
    session: AsyncSession, owner_id: int, model_id: int | None
) -> None:
    if model_id is None:
        return
    row = await session.scalar(
        select(UserStudioModel.id).where(
            UserStudioModel.id == model_id,
            UserStudioModel.user_id == owner_id,
        )
    )
    if not row:
        raise HTTPException(status_code=400, detail="Модель не найдена")
