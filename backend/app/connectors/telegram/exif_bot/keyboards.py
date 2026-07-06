"""Клавиатуры EXIF-бота."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.config import settings
from app.db.models import ExifBotProfile
from app.services.studio_camera_presets import list_camera_presets


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📷 Обработать фото", callback_data="exif:menu:process"),
            ],
            [
                InlineKeyboardButton(text="👤 Мои профили", callback_data="exif:menu:profiles"),
                InlineKeyboardButton(text="➕ Создать профиль", callback_data="exif:menu:create"),
            ],
            [
                InlineKeyboardButton(text="📊 Лимит", callback_data="exif:menu:limits"),
                InlineKeyboardButton(text="❓ Помощь", callback_data="exif:menu:help"),
            ],
        ]
    )


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✖ Отмена", callback_data="exif:cancel")],
        ]
    )


def geo_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Без GPS", callback_data="exif:geo:skip")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data="exif:cancel")],
        ]
    )


def location_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Отправить геолокацию", request_location=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[]], resize_keyboard=True)


def preset_brand_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🍎 iPhone", callback_data="exif:preset_brand:iphone"),
                InlineKeyboardButton(text="📱 Другие", callback_data="exif:preset_brand:other"),
            ],
            [InlineKeyboardButton(text="✖ Отмена", callback_data="exif:cancel")],
        ]
    )


def preset_picker_kb(
    page: int = 0,
    per_page: int = 6,
    *,
    iphone_only: bool | None = True,
) -> InlineKeyboardMarkup:
    presets = list_camera_presets(iphone_only=iphone_only)
    start = page * per_page
    chunk = presets[start : start + per_page]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(chunk), 2):
        pair = chunk[i : i + 2]
        row = [
            InlineKeyboardButton(
                text=p["label"][:40],
                callback_data=f"exif:preset:{p['id']}",
            )
            for p in pair
        ]
        rows.append(row)
    nav: list[InlineKeyboardButton] = []
    brand_tag = "iphone" if iphone_only is True else "other" if iphone_only is False else "all"
    if start > 0:
        nav.append(
            InlineKeyboardButton(
                text="◀",
                callback_data=f"exif:preset_page:{page - 1}:{brand_tag}",
            )
        )
    if start + per_page < len(presets):
        nav.append(
            InlineKeyboardButton(
                text="▶",
                callback_data=f"exif:preset_page:{page + 1}:{brand_tag}",
            )
        )
    if nav:
        rows.append(nav)
    rows.append(
        [
            InlineKeyboardButton(text="« К категориям", callback_data="exif:preset_brand:back"),
        ]
    )
    rows.append([InlineKeyboardButton(text="✖ Отмена", callback_data="exif:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def limits_kb(*, channel_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📣 Подписаться на канал", url=channel_url)],
            [InlineKeyboardButton(text="🔄 Проверить подписку", callback_data="exif:check_sub")],
            [InlineKeyboardButton(text="« Меню", callback_data="exif:menu:home")],
        ]
    )


def limit_exceeded_kb(*, channel_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📣 Подписаться", url=channel_url)],
            [InlineKeyboardButton(text="🔄 Проверить подписку", callback_data="exif:check_sub")],
            [InlineKeyboardButton(text="« Меню", callback_data="exif:menu:home")],
        ]
    )


def profiles_list_kb(profiles: list[ExifBotProfile], *, action: str) -> InlineKeyboardMarkup:
    """action: pick | manage"""
    rows: list[list[InlineKeyboardButton]] = []
    for p in profiles:
        label = (p.title or f"#{p.id}")[:36]
        if action == "pick":
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"📱 {label}",
                        callback_data=f"exif:pick:{p.id}",
                    )
                ]
            )
        else:
            rows.append(
                [
                    InlineKeyboardButton(text=f"📱 {label}", callback_data=f"exif:view:{p.id}"),
                    InlineKeyboardButton(text="🗑", callback_data=f"exif:del:{p.id}"),
                ]
            )
    rows.append([InlineKeyboardButton(text="« Меню", callback_data="exif:menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def camera_pick_kb(profile_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🤳 Селфи (фронталка)",
                    callback_data=f"exif:camera:{profile_id}:selfie",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📸 Основная камера",
                    callback_data=f"exif:camera:{profile_id}:main",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔀 Авто",
                    callback_data=f"exif:camera:{profile_id}:auto",
                ),
            ],
            [InlineKeyboardButton(text="✖ Отмена", callback_data="exif:cancel")],
        ]
    )


def skip_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить (только пресет)", callback_data="exif:main:skip")],
            [InlineKeyboardButton(text="✖ Отмена", callback_data="exif:cancel")],
        ]
    )


def limits_hint_short() -> str:
    return (
        f"Лимит: **{settings.exif_bot_daily_limit_default}** фото/сутки, "
        f"с подпиской на канал ModelMate — **{settings.exif_bot_daily_limit_subscribed}** "
        f"(команда /limits)."
    )
