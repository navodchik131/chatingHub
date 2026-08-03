"""Скачивание изображений из Telegram-сообщений."""

from __future__ import annotations

import logging
from io import BytesIO

from aiogram import Bot
from aiogram.types import Message

log = logging.getLogger(__name__)


async def download_telegram_image(message: Message, bot: Bot) -> tuple[bytes, str, bool] | None:
    file_id: str | None = None
    mime = "image/jpeg"
    is_video_note = False
    if message.photo:
        file_id = message.photo[-1].file_id
        mime = "image/jpeg"
    elif message.sticker:
        st = message.sticker
        if st.is_animated or st.is_video:
            thumb = getattr(st, "thumbnail", None) or getattr(st, "thumb", None)
            if thumb is not None:
                file_id = thumb.file_id
                mime = "image/jpeg"
            else:
                return None
        else:
            file_id = st.file_id
            mime = "image/webp"
    elif message.video_note:
        file_id = message.video_note.file_id
        mime = "video/mp4"
        is_video_note = True
    elif message.animation:
        file_id = message.animation.file_id
        mime = (message.animation.mime_type or "video/mp4").split(";")[0].strip() or "video/mp4"
    elif message.video:
        file_id = message.video.file_id
        mime = (message.video.mime_type or "video/mp4").split(";")[0].strip() or "video/mp4"
    elif message.document:
        doc = message.document
        m = (doc.mime_type or "").lower()
        if m.startswith("image/") or m.startswith("video/"):
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
        return data, mime, is_video_note
    except Exception as e:
        log.warning("telegram image download failed: %s", e)
        return None
