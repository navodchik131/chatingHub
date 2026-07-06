"""Скачивание файлов для EXIF-бота."""

from __future__ import annotations

import logging
from io import BytesIO

from aiogram import Bot
from aiogram.types import Message

from app.config import settings

log = logging.getLogger(__name__)

_FILE_HINT = (
    "Отправьте изображение **файлом** (📎 → Файл), не как сжатое «Фото» — "
    "иначе Telegram удалит EXIF."
)


async def download_image_from_message(message: Message, bot: Bot) -> tuple[bytes, bool]:
    """
    Возвращает (bytes, is_document).
    is_document=False если пришло сжатое photo — EXIF может быть потерян.
    """
    max_bytes = int(settings.exif_bot_max_image_bytes)

    if message.document:
        mime = (message.document.mime_type or "").lower()
        if not mime.startswith("image/"):
            raise ValueError("Нужен файл изображения (JPEG, PNG…).")
        tg_file = await bot.get_file(message.document.file_id)
        if not tg_file.file_path:
            raise ValueError("Не удалось получить файл из Telegram.")
        buf = BytesIO()
        await bot.download_file(tg_file.file_path, buf)
        data = buf.getvalue()
        if len(data) > max_bytes:
            raise ValueError(
                f"Файл слишком большой (макс. {max_bytes // (1024 * 1024)} МБ)."
            )
        if not data:
            raise ValueError("Пустой файл.")
        return data, True

    if message.photo:
        photo = message.photo[-1]
        tg_file = await bot.get_file(photo.file_id)
        if not tg_file.file_path:
            raise ValueError("Не удалось скачать фото.")
        buf = BytesIO()
        await bot.download_file(tg_file.file_path, buf)
        data = buf.getvalue()
        if len(data) > max_bytes:
            raise ValueError(
                f"Файл слишком большой (макс. {max_bytes // (1024 * 1024)} МБ)."
            )
        if not data:
            raise ValueError("Пустой файл.")
        return data, False

    raise ValueError(f"Пришлите изображение файлом.\n\n{_FILE_HINT}")


def file_hint_markdown() -> str:
    return _FILE_HINT
