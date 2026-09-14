"""Извлечь fan chat id из пересланного сообщения (private DM фана)."""

from __future__ import annotations

from aiogram.types import Message


def fan_chat_id_from_forward(message: Message) -> int | None:
    """В личке chat_id фана совпадает с user id."""
    if message.forward_from:
        return int(message.forward_from.id)
    origin = message.forward_origin
    if origin is not None:
        otype = getattr(origin, "type", None)
        if otype == "user":
            sender = getattr(origin, "sender_user", None)
            if sender is not None:
                return int(sender.id)
    return None
