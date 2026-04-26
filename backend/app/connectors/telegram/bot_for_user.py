"""Создание Bot для запросов к Telegram API от имени владельца (legacy или SaaS)."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.connectors.telegram.state import get_bot
from app.db.models import TelegramConnection
from app.services.crypto_secret import decrypt_secret

log = logging.getLogger(__name__)


async def open_telegram_bot_for_owner(
    session: AsyncSession, owner_user_id: int
) -> tuple[Bot | None, bool]:
    """
    Возвращает (bot, need_close).
    Если need_close=True, после использования вызовите await bot.session.close().
    """
    legacy = get_bot()
    if legacy is not None:
        return legacy, False
    row = await session.scalar(
        select(TelegramConnection).where(
            TelegramConnection.user_id == owner_user_id,
            TelegramConnection.is_active.is_(True),
        )
    )
    if not row:
        return None, False
    try:
        token = decrypt_secret(row.bot_token_encrypted)
    except ValueError:
        log.warning("telegram bot token decrypt failed user_id=%s", owner_user_id)
        return None, False
    proxy = (settings.telegram_proxy or "").strip()
    session_aio = AiohttpSession(proxy=proxy) if proxy else None
    bot = Bot(token=token, session=session_aio) if session_aio else Bot(token=token)
    return bot, True


async def telegram_profile_photo_file_id(bot: Bot, telegram_user_id: int | None) -> str | None:
    if telegram_user_id is None:
        return None
    try:
        photos = await bot.get_user_profile_photos(telegram_user_id, limit=1)
    except TelegramBadRequest as e:
        log.debug("get_user_profile_photos failed user_id=%s: %s", telegram_user_id, e)
        return None
    except Exception as e:
        log.warning("get_user_profile_photos error user_id=%s: %s", telegram_user_id, e)
        return None
    if not photos.total_count or not photos.photos:
        return None
    try:
        return photos.photos[0][0].file_id
    except (IndexError, TypeError):
        return None
