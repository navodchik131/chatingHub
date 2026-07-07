"""Клавиатуры Instagram download-бота."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.config import settings

BTN_DOWNLOAD = "📥 Скачать видео"
BTN_LIMITS = "📊 Лимит"
BTN_HELP = "❓ Помощь"
BTN_MENU = "🏠 Меню"

MENU_BUTTONS = frozenset({BTN_DOWNLOAD, BTN_LIMITS, BTN_HELP, BTN_MENU})


def reply_menu_kb() -> ReplyKeyboardMarkup:
    """Постоянное меню внизу чата."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_DOWNLOAD)],
            [
                KeyboardButton(text=BTN_LIMITS),
                KeyboardButton(text=BTN_HELP),
            ],
            [KeyboardButton(text=BTN_MENU)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Ссылка на Reels или пост Instagram…",
    )


def main_menu_kb() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=BTN_DOWNLOAD,
                callback_data="ig:menu:download",
            ),
        ],
        [
            InlineKeyboardButton(text=BTN_LIMITS, callback_data="ig:menu:limits"),
            InlineKeyboardButton(text=BTN_HELP, callback_data="ig:menu:help"),
        ],
    ]
    channel_url = (settings.ig_bot_subscribe_channel_url or "").strip()
    if channel_url:
        rows.append([InlineKeyboardButton(text="📢 Канал ModelMate", url=channel_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def limits_kb(*, channel_url: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="✅ Проверить подписку",
                callback_data="ig:check_sub",
            ),
        ],
    ]
    if channel_url:
        rows.append([InlineKeyboardButton(text="📢 Подписаться на канал", url=channel_url)])
    rows.append([InlineKeyboardButton(text=BTN_MENU, callback_data="ig:menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def limit_exceeded_kb(*, channel_url: str) -> InlineKeyboardMarkup:
    return limits_kb(channel_url=channel_url)


def limits_hint_short() -> str:
    channel = (settings.ig_bot_subscribe_channel_label or settings.ig_bot_subscribe_channel or "").strip()
    channel_part = f" на {channel}" if channel else ""
    return (
        f"Лимит: **{settings.ig_bot_daily_limit_default}** видео/сутки, "
        f"с подпиской{channel_part} — **{settings.ig_bot_daily_limit_subscribed}** "
        f"(UTC, сброс в полночь)."
    )
