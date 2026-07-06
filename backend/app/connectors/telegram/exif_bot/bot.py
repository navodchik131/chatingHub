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


async def verify_exif_bot_channel_access(bot: Bot) -> None:
    """Проверяет, что бот видит канал подписки (нужны права админа для getChatMember)."""
    channel = (settings.exif_bot_subscribe_channel or "").strip()
    if not channel:
        log.warning("EXIF bot: EXIF_BOT_SUBSCRIBE_CHANNEL not set — bonus limit disabled")
        return
    me = await bot.get_me()
    try:
        chat = await bot.get_chat(channel)
        member = await bot.get_chat_member(chat.id, me.id)
        status = str(getattr(member, "status", "") or "")
        if status not in ("administrator", "creator"):
            log.warning(
                "EXIF bot @%s is NOT admin in channel %s (status=%s). "
                "Subscription check will fail — add this bot as channel admin.",
                me.username,
                channel,
                status,
            )
        else:
            log.info(
                "EXIF bot @%s channel OK: %s (id=%s)",
                me.username,
                getattr(chat, "title", channel),
                chat.id,
            )
    except Exception as e:
        log.warning(
            "EXIF bot cannot access subscribe channel %s: %s",
            channel,
            e,
        )


async def run_exif_bot_polling() -> None:
    token = settings.exif_bot_token.strip()
    if not token:
        return
    bot = create_exif_bot()
    try:
        me = await bot.get_me()
        log.info(
            "EXIF bot polling: @%s | limits default=%s subscribed=%s channel=%s",
            me.username,
            settings.exif_bot_daily_limit_default,
            settings.exif_bot_daily_limit_subscribed,
            settings.exif_bot_subscribe_channel,
        )
        await verify_exif_bot_channel_access(bot)
        await exif_dp.start_polling(bot)
    finally:
        await bot.session.close()
        log.info("EXIF bot stopped")
