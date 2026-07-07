"""Запуск polling Instagram download-бота."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from app.config import settings
from app.connectors.telegram.ig_bot.setup import ig_dp

log = logging.getLogger(__name__)


def create_ig_bot() -> Bot:
    token = settings.ig_bot_token.strip()
    proxy = (settings.telegram_proxy or "").strip()
    if proxy:
        session = AiohttpSession(proxy=proxy)
        return Bot(token=token, session=session)
    return Bot(token=token)


async def verify_ig_bot_channel_access(bot: Bot) -> None:
    channel = (settings.ig_bot_subscribe_channel or "").strip()
    if not channel:
        log.warning("IG bot: IG_BOT_SUBSCRIBE_CHANNEL not set — bonus limit disabled")
        return
    me = await bot.get_me()
    try:
        chat = await bot.get_chat(channel)
        member = await bot.get_chat_member(chat.id, me.id)
        status = str(getattr(member, "status", "") or "")
        if status not in ("administrator", "creator"):
            log.warning(
                "IG bot @%s is NOT admin in channel %s (status=%s).",
                me.username,
                channel,
                status,
            )
        else:
            log.info(
                "IG bot @%s channel OK: %s (id=%s)",
                me.username,
                getattr(chat, "title", channel),
                chat.id,
            )
    except Exception as e:
        log.warning("IG bot cannot access subscribe channel %s: %s", channel, e)


async def run_ig_bot_polling() -> None:
    token = settings.ig_bot_token.strip()
    if not token:
        return
    cookies = (settings.ig_bot_cookies_path or "").strip()
    if not cookies:
        log.warning("IG bot: IG_BOT_COOKIES_PATH not set — downloads will fail")
    bot = create_ig_bot()
    try:
        me = await bot.get_me()
        log.info(
            "IG bot polling: @%s | limits default=%s subscribed=%s channel=%s cookies=%s",
            me.username,
            settings.ig_bot_daily_limit_default,
            settings.ig_bot_daily_limit_subscribed,
            settings.ig_bot_subscribe_channel,
            "yes" if cookies else "no",
        )
        await verify_ig_bot_channel_access(bot)
        await ig_dp.start_polling(bot)
    finally:
        await bot.session.close()
        log.info("IG bot stopped")
