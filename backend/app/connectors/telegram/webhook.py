"""Регистрация Telegram webhook (SaaS)."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from sqlalchemy import select

from app.config import settings
from app.db.models import TelegramConnection
from app.db.session import SessionLocal
from app.services.crypto_secret import decrypt_secret

log = logging.getLogger(__name__)

# Явный список: message + реакции собеседника (Bot API 7+).
TELEGRAM_WEBHOOK_ALLOWED_UPDATES = [
    "message",
    "edited_message",
    "message_reaction",
]


async def register_telegram_webhook(
    bot: Bot,
    url: str,
    *,
    drop_pending_updates: bool = False,
) -> None:
    await bot.set_webhook(
        url,
        drop_pending_updates=drop_pending_updates,
        allowed_updates=TELEGRAM_WEBHOOK_ALLOWED_UPDATES,
    )


async def refresh_registered_telegram_webhooks() -> None:
    """Обновить allowed_updates у уже зарегистрированных webhook (после деплоя)."""
    public_base = settings.public_app_url.strip().rstrip("/")
    if not public_base.lower().startswith("https://"):
        return
    async with SessionLocal() as session:
        rows = (
            await session.scalars(
                select(TelegramConnection).where(
                    TelegramConnection.is_active.is_(True),
                    TelegramConnection.webhook_registered.is_(True),
                )
            )
        ).all()
        if not rows:
            return
        proxy = (settings.telegram_proxy or "").strip()
        session_aio = AiohttpSession(proxy=proxy) if proxy else None
        for row in rows:
            wh_url = f"{public_base}/api/webhooks/telegram/{row.webhook_secret}"
            try:
                token = decrypt_secret(row.bot_token_encrypted)
            except Exception:
                log.warning("telegram webhook refresh: decrypt failed user=%s", row.user_id)
                continue
            bot = Bot(token=token, session=session_aio) if session_aio else Bot(token=token)
            try:
                await register_telegram_webhook(bot, wh_url, drop_pending_updates=False)
                log.info("telegram webhook refreshed user=%s", row.user_id)
            except Exception:
                log.warning("telegram webhook refresh failed user=%s", row.user_id, exc_info=True)
            finally:
                await bot.session.close()
        if session_aio:
            await session_aio.close()
