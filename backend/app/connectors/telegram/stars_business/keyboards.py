"""Клавиатуры OPERATOR."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.connectors.telegram.stars_business.fan_window import chat_window_open, window_label
from app.db.models import StarsBusinessFanChat


def operator_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Отправить paid media", callback_data="sb:paid")],
            [InlineKeyboardButton(text="📋 Недавние диалоги", callback_data="sb:chats")],
        ]
    )


def fan_pick_kb(chats: list[StarsBusinessFanChat]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for c in chats[:20]:
        open_ = chat_window_open(c.last_inbound_at)
        name = (c.fan_display_name or f"chat {c.fan_chat_id}").strip()[:40]
        mark = "🟢" if open_ else "🔴"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark} {name}",
                    callback_data=f"sb:fan:{c.fan_chat_id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="sb:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_send_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Отправить", callback_data=f"sb:send:{order_id}"),
                InlineKeyboardButton(text="Отмена", callback_data="sb:cancel"),
            ]
        ]
    )


def format_fan_list(chats: list[StarsBusinessFanChat]) -> str:
    if not chats:
        return "Пока нет кэша диалогов. Дождитесь входящих business_message или перешлите сообщение фана."
    lines = ["<b>Недавние диалоги OWNER ↔ фан</b>\n"]
    for c in chats[:15]:
        open_ = chat_window_open(c.last_inbound_at)
        name = (c.fan_display_name or f"id {c.fan_chat_id}").strip()
        lines.append(f"• {name} — {window_label(open_)}")
    lines.append("\nПерешлите сообщение фана или выберите из списка в /paid.")
    return "\n".join(lines)
