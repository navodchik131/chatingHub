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


def _fanvue_headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {(access_token or '').strip()}",
        "X-Fanvue-API-Version": settings.fanvue_api_version,
    }


def _fanvue_base_url() -> str:
    return (settings.fanvue_api_base or "https://api.fanvue.com").rstrip("/")


async def fanvue_api_get(
    access_token: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
) -> Any:
    token = (access_token or "").strip()
    if not token:
        raise FanvueAPIError(503, "Fanvue access token is not set")
    url = f"{_fanvue_base_url()}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url, headers=_fanvue_headers(token), params=params)
    if r.status_code >= 400:
        log.warning("fanvue GET %s failed: %s %s", path, r.status_code, r.text[:800])
        raise FanvueAPIError(r.status_code, r.text)
    try:
        return r.json()
    except Exception as e:
        raise FanvueAPIError(r.status_code, "invalid json response") from e


def fanvue_api_data_list(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return data
        items = payload.get("items")
        if isinstance(items, list):
            return items
    return []


def fanvue_api_has_more(payload: Any, *, page: int, page_size: int, fetched: int) -> bool:
    if isinstance(payload, dict):
        pag = payload.get("pagination") or payload.get("meta") or {}
        if isinstance(pag, dict):
            for key in ("hasMore", "has_more"):
                if key in pag:
                    return bool(pag[key])
            total_pages = pag.get("totalPages") or pag.get("total_pages")
            if total_pages is not None:
                try:
                    return page < int(total_pages)
                except (TypeError, ValueError):
                    pass
    return fetched >= page_size


async def list_fanvue_chats(
    access_token: str,
    *,
    page: int = 1,
    size: int = 50,
) -> Any:
    return await fanvue_api_get(access_token, "/chats", params={"page": page, "size": size})


async def list_fanvue_chat_messages(
    access_token: str,
    fan_user_uuid: str,
    *,
    page: int = 1,
    size: int = 50,
) -> Any:
    fan = (fan_user_uuid or "").strip()
    if not fan:
        raise FanvueAPIError(400, "empty fan user uuid")
    return await fanvue_api_get(
        access_token,
        f"/chats/{fan}/messages",
        params={"page": page, "size": size},
    )


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

    base = _fanvue_base_url()
    url = f"{base}/chats/{fan_user_uuid}/message"
    headers = {
        **_fanvue_headers(token),
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
