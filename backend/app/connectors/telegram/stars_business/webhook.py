"""Webhook Stars Business (отдельный от SaaS telegram_connections)."""

from __future__ import annotations

import logging

from aiogram import Bot

log = logging.getLogger(__name__)

STARS_BUSINESS_ALLOWED_UPDATES = [
    "message",
    "callback_query",  # inline-кнопки OPERATOR (/paid, подтверждение)
    "business_connection",
    "business_message",
    "edited_business_message",
    "purchased_paid_media",
]


async def register_stars_business_webhook(
    bot: Bot,
    url: str,
    *,
    drop_pending_updates: bool = False,
) -> None:
    await bot.set_webhook(
        url,
        drop_pending_updates=drop_pending_updates,
        allowed_updates=STARS_BUSINESS_ALLOWED_UPDATES,
    )
    log.info("stars business webhook registered")
