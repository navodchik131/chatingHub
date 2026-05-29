"""HTTP-клиент Fanvue API: отправка сообщений в чат."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class FanvueAPIError(Exception):
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body
        super().__init__(f"Fanvue API {status}: {body[:500]}")


async def send_direct_message(
    access_token: str,
    fan_user_uuid: str,
    text: str,
    *,
    media_uuids: list[str] | None = None,
) -> str:
    token = (access_token or "").strip()
    if not token:
        raise FanvueAPIError(503, "Fanvue access token is not set")

    base = (settings.fanvue_api_base or "https://api.fanvue.com").rstrip("/")
    url = f"{base}/chats/{fan_user_uuid}/message"
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Fanvue-API-Version": settings.fanvue_api_version,
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {"text": text or ""}
    if media_uuids:
        payload["mediaUuids"] = [u for u in media_uuids if u]
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, json=payload, headers=headers)
    if r.status_code >= 400:
        log.warning("fanvue send failed: %s %s", r.status_code, r.text[:800])
        raise FanvueAPIError(r.status_code, r.text)

    try:
        data = r.json()
    except Exception:
        return ""
    return str(data.get("messageUuid") or "")
