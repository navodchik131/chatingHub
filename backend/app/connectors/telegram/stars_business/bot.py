"""Запуск Stars Business bot: webhook / polling."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from app.config import settings
from app.connectors.telegram.stars_business.setup import stars_business_dp
from app.connectors.telegram.stars_business.webhook import (
    STARS_BUSINESS_ALLOWED_UPDATES,
    register_stars_business_webhook,
)

log = logging.getLogger(__name__)


def create_stars_business_bot() -> Bot:
    token = settings.stars_business_bot_token.strip()
    proxy = (settings.telegram_proxy or "").strip()
    if proxy:
        return Bot(token=token, session=AiohttpSession(proxy=proxy))
    return Bot(token=token)


async def run_stars_business_polling() -> None:
    token = settings.stars_business_bot_token.strip()
    if not token:
        return
    bot = create_stars_business_bot()
    me = await bot.get_me()
    log.info("Stars Business bot polling @%s", me.username)
    await stars_business_dp.start_polling(bot, allowed_updates=STARS_BUSINESS_ALLOWED_UPDATES)


async def setup_stars_business_webhook() -> None:
    if not settings.stars_business_configured:
        return
    secret = (settings.stars_business_webhook_secret or "").strip()
    if not secret:
        log.warning("STARS_BUSINESS_WEBHOOK_SECRET пуст — webhook не регистрируется")
        return
    public_base = (settings.public_app_url or "").strip().rstrip("/")
    if not public_base.lower().startswith("https://"):
        log.warning("PUBLIC_APP_URL без HTTPS — Stars Business webhook пропущен (используйте STARS_BUSINESS_POLLING=1)")
        return
    bot = create_stars_business_bot()
    url = f"{public_base}/api/webhooks/telegram-stars/{secret}"
    await register_stars_business_webhook(bot, url)
    me = await bot.get_me()
    log.info("Stars Business webhook @%s → %s", me.username, url)
