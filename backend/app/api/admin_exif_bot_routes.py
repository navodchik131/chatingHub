"""API EXIF Telegram-бота в админке."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_platform_admin
from app.db.models import User
from app.db.session import get_session
from app.schemas import AdminExifBotStatsOut, AdminExifBotUserDetailOut, AdminExifBotUserRow
from app.services.admin_exif_bot import (
    build_exif_bot_admin_stats,
    get_exif_bot_admin_user_detail,
    list_exif_bot_admin_users,
)

router = APIRouter(tags=["admin-exif-bot"])


@router.get("/admin/exif-bot/stats", response_model=AdminExifBotStatsOut)
async def admin_exif_bot_stats(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
) -> AdminExifBotStatsOut:
    return await build_exif_bot_admin_stats(session)


@router.get("/admin/exif-bot/users", response_model=list[AdminExifBotUserRow])
async def admin_exif_bot_users(
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
    q: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[AdminExifBotUserRow]:
    return await list_exif_bot_admin_users(session, q=q, limit=limit, offset=offset)


@router.get("/admin/exif-bot/users/{user_id}", response_model=AdminExifBotUserDetailOut)
async def admin_exif_bot_user_detail(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(get_platform_admin),
) -> AdminExifBotUserDetailOut:
    row = await get_exif_bot_admin_user_detail(session, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Пользователь EXIF-бота не найден")
    return row
