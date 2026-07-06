"""Запуск polling EXIF-бота."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from app.config import settings
from app.connectors.telegram.exif_bot.setup import exif_dp

log = logging.getLogger(__name__)


def create_exif_bot() -> Bot:
    token = settings.exif_bot_token.strip()
    proxy = (settings.telegram_proxy or "").strip()
    if proxy:
        session = AiohttpSession(proxy=proxy)
        return Bot(token=token, session=session)
    return Bot(token=token)


async def run_exif_bot_polling() -> None:
    token = settings.exif_bot_token.strip()
    if not token:
        return
    bot = create_exif_bot()
    try:
        me = await bot.get_me()
        log.info("EXIF bot polling: @%s", me.username)
        await exif_dp.start_polling(bot)
    finally:
        await bot.session.close()
        log.info("EXIF bot stopped")
