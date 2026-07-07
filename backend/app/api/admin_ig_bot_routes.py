"""API Instagram download Telegram-бота в админке."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_platform_admin
from app.db.models import User
from app.db.session import get_session
from app.schemas import AdminIgBotStatsOut, AdminIgBotUserDetailOut, AdminIgBotUserRow
from app.services.admin_ig_bot import (
    build_ig_bot_admin_stats,
    get_ig_bot_admin_user_detail,
    list_ig_bot_admin_users,
)

router = APIRouter(tags=["admin-ig-bot"])


@router.get("/admin/ig-bot/stats", response_model=AdminIgBotStatsOut)
async def admin_ig_bot_stats(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
) -> AdminIgBotStatsOut:
    return await build_ig_bot_admin_stats(session)


@router.get("/admin/ig-bot/users", response_model=list[AdminIgBotUserRow])
async def admin_ig_bot_users(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[AdminIgBotUserRow]:
    return await list_ig_bot_admin_users(session, q=q, limit=limit, offset=offset)


@router.get("/admin/ig-bot/users/{user_id}", response_model=AdminIgBotUserDetailOut)
async def admin_ig_bot_user_detail(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
) -> AdminIgBotUserDetailOut:
    row = await get_ig_bot_admin_user_detail(session, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Пользователь IG-бота не найден")
    return row
