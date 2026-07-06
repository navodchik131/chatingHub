"""Репозиторий пользователей и профилей EXIF-бота."""

from __future__ import annotations

from datetime import datetime, timezone

from aiogram.types import User as TgUser
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.models import ExifBotProfile, ExifBotUser


async def get_or_create_exif_bot_user(session: AsyncSession, tg: TgUser) -> ExifBotUser:
    row = await session.scalar(
        select(ExifBotUser).where(ExifBotUser.telegram_id == tg.id)
    )
    if row:
        row.username = tg.username
        row.first_name = tg.first_name
        row.last_name = tg.last_name
        row.language_code = tg.language_code
        row.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return row
    row = ExifBotUser(
        telegram_id=tg.id,
        username=tg.username,
        first_name=tg.first_name,
        last_name=tg.last_name,
        language_code=tg.language_code,
    )
    session.add(row)
    await session.flush()
    return row


async def count_profiles(session: AsyncSession, user_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(ExifBotProfile)
            .where(ExifBotProfile.user_id == user_id)
        )
        or 0
    )


async def list_profiles(session: AsyncSession, user_id: int) -> list[ExifBotProfile]:
    return list(
        (
            await session.scalars(
                select(ExifBotProfile)
                .where(ExifBotProfile.user_id == user_id)
                .order_by(ExifBotProfile.id.asc())
            )
        ).all()
    )


async def get_profile_for_user(
    session: AsyncSession,
    *,
    user_id: int,
    profile_id: int,
) -> ExifBotProfile | None:
    return await session.scalar(
        select(ExifBotProfile).where(
            ExifBotProfile.id == profile_id,
            ExifBotProfile.user_id == user_id,
        )
    )


async def create_profile(
    session: AsyncSession,
    *,
    user_id: int,
    title: str,
    camera_preset_id: str | None,
    phone_exif_selfie_json: str | None,
    phone_exif_main_json: str | None,
    export_lat: float | None,
    export_lon: float | None,
) -> ExifBotProfile:
    cap = int(settings.exif_bot_max_profiles_per_user)
    n = await count_profiles(session, user_id)
    if n >= cap:
        raise ValueError(f"Максимум {cap} профилей")
    row = ExifBotProfile(
        user_id=user_id,
        title=title.strip()[:120],
        camera_preset_id=camera_preset_id,
        phone_exif_selfie_json=phone_exif_selfie_json,
        phone_exif_main_json=phone_exif_main_json,
        export_lat=export_lat,
        export_lon=export_lon,
    )
    session.add(row)
    await session.flush()
    return row


async def delete_profile(
    session: AsyncSession,
    *,
    user_id: int,
    profile_id: int,
) -> bool:
    row = await get_profile_for_user(session, user_id=user_id, profile_id=profile_id)
    if not row:
        return False
    await session.delete(row)
    return True


async def load_user_with_profiles(
    session: AsyncSession, telegram_id: int
) -> ExifBotUser | None:
    return await session.scalar(
        select(ExifBotUser)
        .where(ExifBotUser.telegram_id == telegram_id)
        .options(selectinload(ExifBotUser.profiles))
    )
