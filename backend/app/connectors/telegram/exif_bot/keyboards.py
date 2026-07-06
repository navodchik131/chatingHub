"""Клавиатуры EXIF-бота."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

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


def preset_picker_kb(page: int = 0, per_page: int = 6) -> InlineKeyboardMarkup:
    presets = list_camera_presets()
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
    if start > 0:
        nav.append(InlineKeyboardButton(text="◀", callback_data=f"exif:preset_page:{page - 1}"))
    if start + per_page < len(presets):
        nav.append(InlineKeyboardButton(text="▶", callback_data=f"exif:preset_page:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="✖ Отмена", callback_data="exif:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
