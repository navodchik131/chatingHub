"""Пользователи Instagram download-бота."""

from __future__ import annotations

from aiogram.types import User as TgUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IgBotUser


async def get_or_create_ig_bot_user(session: AsyncSession, tg: TgUser) -> IgBotUser:
    row = await session.scalar(
        select(IgBotUser).where(IgBotUser.telegram_id == tg.id)
    )
    if row is not None:
        row.username = tg.username
        row.first_name = tg.first_name
        row.last_name = tg.last_name
        row.language_code = tg.language_code
        session.add(row)
        await session.flush()
        return row

    row = IgBotUser(
        telegram_id=tg.id,
        username=tg.username,
        first_name=tg.first_name,
        last_name=tg.last_name,
        language_code=tg.language_code,
    )
    session.add(row)
    await session.flush()
    return row
