"""Статус недоступного собеседника Fanvue (удалён / заблокирован на платформе)."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation

log = logging.getLogger(__name__)

FANVUE_PEER_UNAVAILABLE_DETAIL = (
    "Пользователь Fanvue недоступен: аккаунт удалён или заблокирован на платформе. "
    "Отправка сообщений невозможна — диалог можно убрать из списка."
)


def fanvue_api_body_indicates_invalid_user(body: str) -> bool:
    raw = (body or "").strip()
    if not raw:
        return False
    lower = raw.lower()
    if "invalid user uuid" in lower:
        return True
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(data, dict):
        return False
    for key in ("message", "error", "detail"):
        val = data.get(key)
        if isinstance(val, str) and "invalid user uuid" in val.lower():
            return True
    return False


def fanvue_peer_unavailable_http_exception() -> HTTPException:
    return HTTPException(status_code=410, detail=FANVUE_PEER_UNAVAILABLE_DETAIL)


async def mark_conversation_peer_unavailable(
    session: AsyncSession,
    conv: Conversation,
) -> bool:
    if conv.peer_unavailable:
        return False
    conv.peer_unavailable = True
    await session.flush()
    log.info(
        "fanvue peer unavailable conv=%s platform=%s fan=%s",
        conv.id,
        conv.platform.value,
        (conv.external_chat_id or "")[:8],
    )
    return True
