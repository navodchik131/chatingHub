"""Аналитика EXIF Telegram-бота для админ-панели."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ExifBotProfile, ExifBotUser
from app.schemas import AdminExifBotStatsOut, AdminExifBotUserDetailOut, AdminExifBotUserRow, AdminExifBotProfileRow
from app.services.exif_bot.limits import _utc_today, effective_total_process_count
from app.services.exif_bot.process import profile_is_ready


def _display_name(u: ExifBotUser) -> str:
    parts = [p for p in (u.first_name, u.last_name) if p]
    if parts:
        return " ".join(parts)
    if u.username:
        return f"@{u.username}"
    return f"TG {u.telegram_id}"


def _telegram_link(u: ExifBotUser) -> str | None:
    if u.username:
        return f"https://t.me/{u.username}"
    return None


def _row_from_user(u: ExifBotUser, *, profiles_count: int) -> AdminExifBotUserRow:
    today = _utc_today()
    used_today = int(u.daily_process_count or 0) if (u.daily_process_day or "") == today else 0
    return AdminExifBotUserRow(
        id=u.id,
        telegram_id=int(u.telegram_id),
        username=u.username,
        display_name=_display_name(u),
        telegram_link=_telegram_link(u),
        language_code=u.language_code,
        profiles_count=profiles_count,
        total_process_count=effective_total_process_count(u),
        daily_process_count=used_today,
        daily_process_day=u.daily_process_day,
        created_at=u.created_at,
        updated_at=u.updated_at,
    )


async def build_exif_bot_admin_stats(session: AsyncSession) -> AdminExifBotStatsOut:
    today = _utc_today()
    now = datetime.now(timezone.utc)
    day7 = now - timedelta(days=7)
    day30 = now - timedelta(days=30)

    total_users = int(await session.scalar(select(func.count(ExifBotUser.id))) or 0)
    total_profiles = int(await session.scalar(select(func.count(ExifBotProfile.id))) or 0)
    total_processes = int(
        await session.scalar(select(func.coalesce(func.sum(ExifBotUser.total_process_count), 0))) or 0
    )
    processes_today = int(
        await session.scalar(
            select(func.coalesce(func.sum(ExifBotUser.daily_process_count), 0)).where(
                ExifBotUser.daily_process_day == today
            )
        )
        or 0
    )
    active_7d = int(
        await session.scalar(
            select(func.count(ExifBotUser.id)).where(ExifBotUser.updated_at >= day7)
        )
        or 0
    )
    active_30d = int(
        await session.scalar(
            select(func.count(ExifBotUser.id)).where(ExifBotUser.updated_at >= day30)
        )
        or 0
    )
    users_with_profiles = int(
        await session.scalar(
            select(func.count(func.distinct(ExifBotProfile.user_id)))
        )
        or 0
    )

    return AdminExifBotStatsOut(
        total_users=total_users,
        total_profiles=total_profiles,
        total_processes=total_processes,
        processes_today=processes_today,
        active_users_7d=active_7d,
        active_users_30d=active_30d,
        users_with_profiles=users_with_profiles,
        utc_day=today,
    )


async def list_exif_bot_admin_users(
    session: AsyncSession,
    *,
    q: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[AdminExifBotUserRow]:
    stmt = (
        select(ExifBotUser, func.count(ExifBotProfile.id).label("profiles_count"))
        .outerjoin(ExifBotProfile, ExifBotProfile.user_id == ExifBotUser.id)
        .group_by(ExifBotUser.id)
        .order_by(ExifBotUser.total_process_count.desc(), ExifBotUser.updated_at.desc())
        .limit(min(limit, 500))
        .offset(max(offset, 0))
    )
    needle = (q or "").strip()
    if needle:
        like = f"%{needle.lower()}%"
        filters = [
            func.lower(func.coalesce(ExifBotUser.username, "")).like(like),
            func.lower(func.coalesce(ExifBotUser.first_name, "")).like(like),
            func.lower(func.coalesce(ExifBotUser.last_name, "")).like(like),
        ]
        if needle.isdigit():
            filters.append(ExifBotUser.telegram_id == int(needle))
        stmt = stmt.where(or_(*filters))

    rows = (await session.execute(stmt)).all()
    return [_row_from_user(u, profiles_count=int(pc or 0)) for u, pc in rows]


async def get_exif_bot_admin_user_detail(
    session: AsyncSession,
    user_id: int,
) -> AdminExifBotUserDetailOut | None:
    stmt = (
        select(ExifBotUser)
        .where(ExifBotUser.id == user_id)
        .options(selectinload(ExifBotUser.profiles))
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        return None

    profiles = [
        AdminExifBotProfileRow(
            id=p.id,
            title=p.title or "",
            camera_preset_id=p.camera_preset_id,
            has_selfie_ref=bool(p.phone_exif_selfie_json),
            has_main_ref=bool(p.phone_exif_main_json),
            has_gps=p.export_lat is not None and p.export_lon is not None,
            is_ready=profile_is_ready(p),
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in user.profiles
    ]

    base = _row_from_user(user, profiles_count=len(user.profiles))
    return AdminExifBotUserDetailOut(
        **base.model_dump(),
        profiles=profiles,
    )
