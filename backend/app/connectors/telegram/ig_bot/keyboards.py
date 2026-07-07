"""Клавиатуры Instagram download-бота."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import settings


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📥 Как скачать",
                    callback_data="ig:menu:help",
                ),
            ],
            [
                InlineKeyboardButton(text="📊 Лимит", callback_data="ig:menu:limits"),
            ],
        ]
    )


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
        rows.append([InlineKeyboardButton(text="📢 Канал", url=channel_url)])
    rows.append([InlineKeyboardButton(text="◀️ Меню", callback_data="ig:menu:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def limit_exceeded_kb(*, channel_url: str) -> InlineKeyboardMarkup:
    return limits_kb(channel_url=channel_url)


def limits_hint_short() -> str:
    return (
        f"Лимит: **{settings.ig_bot_daily_limit_default}** видео/сутки, "
        f"с подпиской на канал — **{settings.ig_bot_daily_limit_subscribed}** "
        f"(UTC, сброс в полночь)."
    )
