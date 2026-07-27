"""Polling login-бота (TELEGRAM_LOGIN_BOT_TOKEN)."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from app.config import settings
from app.connectors.telegram.login_bot.setup import login_dp

log = logging.getLogger(__name__)


def create_login_bot() -> Bot:
    token = settings.telegram_login_bot_token.strip()
    proxy = (settings.telegram_proxy or "").strip()
    if proxy:
        session = AiohttpSession(proxy=proxy)
        return Bot(token=token, session=session)
    return Bot(token=token)


async def run_login_bot_polling() -> None:
    token = settings.telegram_login_bot_token.strip()
    if not token:
        return
    bot = create_login_bot()
    me = await bot.get_me()
    log.info("Telegram login bot polling started: @%s", me.username)
    try:
        await login_dp.start_polling(bot)
    finally:
        await bot.session.close()
