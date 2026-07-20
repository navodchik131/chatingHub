"""Отправка push через Expo Push API (мобильное приложение)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.db.repo import delete_mobile_push_token_by_id, list_mobile_push_tokens
from app.db.session import SessionLocal

log = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


async def notify_inbound_message_mobile(
    owner_user_id: int,
    *,
    conversation_id: int,
    title: str,
    body: str,
) -> None:
    async with SessionLocal() as session:
        tokens = await list_mobile_push_tokens(session, owner_user_id)
    if not tokens:
        return

    text = (body or "")[:2000]
    title_t = (title or "Сообщение")[:200]
    messages: list[dict[str, Any]] = [
        {
            "to": t.expo_token,
            "title": title_t,
            "body": text,
            "sound": "default",
            "priority": "high",
            "data": {"conversation_id": conversation_id},
        }
        for t in tokens
    ]

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(EXPO_PUSH_URL, json=messages)
            resp.raise_for_status()
            payload = resp.json()
    except Exception as e:
        log.warning("expo push: %s", e)
        return

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return

    for item, token_row in zip(data, tokens, strict=False):
        if not isinstance(item, dict):
            continue
        status = item.get("status")
        details = item.get("details") or {}
        if status == "error":
            err = str(details.get("error") or "")
            if err in ("DeviceNotRegistered", "InvalidCredentials"):
                async with SessionLocal() as session:
                    await delete_mobile_push_token_by_id(session, token_row.id)
                    await session.commit()
