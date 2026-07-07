"""Аналитика Instagram download Telegram-бота для админ-панели."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import IgBotUser
from app.schemas import AdminIgBotStatsOut, AdminIgBotUserDetailOut, AdminIgBotUserRow
from app.services.ig_bot.limits import _utc_today, effective_total_process_count


def _display_name(u: IgBotUser) -> str:
    parts = [p for p in (u.first_name, u.last_name) if p]
    if parts:
        return " ".join(parts)
    if u.username:
        return f"@{u.username}"
    return f"TG {u.telegram_id}"


def _telegram_link(u: IgBotUser) -> str | None:
    if u.username:
        return f"https://t.me/{u.username}"
    return None


def _row_from_user(u: IgBotUser) -> AdminIgBotUserRow:
    today = _utc_today()
    used_today = int(u.daily_process_count or 0) if (u.daily_process_day or "") == today else 0
    return AdminIgBotUserRow(
        id=u.id,
        telegram_id=int(u.telegram_id),
        username=u.username,
        display_name=_display_name(u),
        telegram_link=_telegram_link(u),
        language_code=u.language_code,
        total_process_count=effective_total_process_count(u),
        daily_process_count=used_today,
        daily_process_day=u.daily_process_day,
        created_at=u.created_at,
        updated_at=u.updated_at,
    )


async def build_ig_bot_admin_stats(session: AsyncSession) -> AdminIgBotStatsOut:
    today = _utc_today()
    now = datetime.now(timezone.utc)
    day7 = now - timedelta(days=7)
    day30 = now - timedelta(days=30)

    total_users = int(await session.scalar(select(func.count(IgBotUser.id))) or 0)
    total_downloads = int(
        await session.scalar(select(func.coalesce(func.sum(IgBotUser.total_process_count), 0))) or 0
    )
    downloads_today = int(
        await session.scalar(
            select(func.coalesce(func.sum(IgBotUser.daily_process_count), 0)).where(
                IgBotUser.daily_process_day == today
            )
        )
        or 0
    )
    active_7d = int(
        await session.scalar(select(func.count(IgBotUser.id)).where(IgBotUser.updated_at >= day7))
        or 0
    )
    active_30d = int(
        await session.scalar(select(func.count(IgBotUser.id)).where(IgBotUser.updated_at >= day30))
        or 0
    )
    users_downloaded_today = int(
        await session.scalar(
            select(func.count(IgBotUser.id)).where(
                IgBotUser.daily_process_day == today,
                IgBotUser.daily_process_count > 0,
            )
        )
        or 0
    )

    return AdminIgBotStatsOut(
        total_users=total_users,
        total_downloads=total_downloads,
        downloads_today=downloads_today,
        active_users_7d=active_7d,
        active_users_30d=active_30d,
        users_downloaded_today=users_downloaded_today,
        daily_limit_default=int(settings.ig_bot_daily_limit_default),
        daily_limit_subscribed=int(settings.ig_bot_daily_limit_subscribed),
        utc_day=today,
    )


async def list_ig_bot_admin_users(
    session: AsyncSession,
    *,
    q: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[AdminIgBotUserRow]:
    stmt = (
        select(IgBotUser)
        .order_by(IgBotUser.total_process_count.desc(), IgBotUser.updated_at.desc())
        .limit(min(limit, 500))
        .offset(max(offset, 0))
    )
    needle = (q or "").strip()
    if needle:
        like = f"%{needle.lower()}%"
        filters = [
            func.lower(func.coalesce(IgBotUser.username, "")).like(like),
            func.lower(func.coalesce(IgBotUser.first_name, "")).like(like),
            func.lower(func.coalesce(IgBotUser.last_name, "")).like(like),
        ]
        if needle.isdigit():
            filters.append(IgBotUser.telegram_id == int(needle))
        stmt = stmt.where(or_(*filters))

    rows = (await session.scalars(stmt)).all()
    return [_row_from_user(u) for u in rows]


async def get_ig_bot_admin_user_detail(
    session: AsyncSession,
    user_id: int,
) -> AdminIgBotUserDetailOut | None:
    user = await session.scalar(select(IgBotUser).where(IgBotUser.id == user_id))
    if user is None:
        return None
    return AdminIgBotUserDetailOut(**_row_from_user(user).model_dump())
