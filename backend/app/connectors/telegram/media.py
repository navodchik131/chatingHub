"""Скачивание изображений из Telegram-сообщений."""

from __future__ import annotations

import logging
from io import BytesIO

from aiogram import Bot
from aiogram.types import Message

log = logging.getLogger(__name__)


async def download_telegram_image(message: Message, bot: Bot) -> tuple[bytes, str] | None:
    file_id: str | None = None
    mime = "image/jpeg"
    if message.photo:
        file_id = message.photo[-1].file_id
        mime = "image/jpeg"
    elif message.document:
        doc = message.document
        m = (doc.mime_type or "").lower()
        if m.startswith("image/"):
            file_id = doc.file_id
            mime = m.split(";")[0].strip() or "image/jpeg"
    if not file_id:
        return None
    try:
        tg_file = await bot.get_file(file_id)
        if not tg_file.file_path:
            return None
        buf = BytesIO()
        await bot.download_file(tg_file.file_path, buf)
        data = buf.getvalue()
        if not data:
            return None
        return data, mime
    except Exception as e:
        log.warning("telegram image download failed: %s", e)
        return None
