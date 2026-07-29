"""Instagram Messaging API client (Graph API with Instagram Login)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger(__name__)


class InstagramAPIError(Exception):
    def __init__(self, message: str, *, status: int = 0, body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def _graph_version() -> str:
    return (settings.instagram_graph_api_version or "v21.0").strip().lstrip("v")


async def send_instagram_message(
    *,
    access_token: str,
    ig_user_id: str,
    recipient_id: str,
    text: str | None = None,
    image_url: str | None = None,
) -> str | None:
    token = (access_token or "").strip()
    ig_id = (ig_user_id or "").strip()
    recipient = (recipient_id or "").strip()
    if not token or not ig_id or not recipient:
        raise InstagramAPIError("missing instagram send parameters")

    message: dict[str, Any] = {}
    txt = (text or "").strip()
    img = (image_url or "").strip()
    if img:
        message["attachment"] = {"type": "image", "payload": {"url": img}}
        if txt:
            message["text"] = txt
    elif txt:
        message["text"] = txt
    else:
        raise InstagramAPIError("empty instagram message")

    body = {"recipient": {"id": recipient}, "message": message}
    ver = _graph_version()
    url = f"https://graph.instagram.com/v{ver}/{ig_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, json=body, headers=headers)
    if r.status_code >= 400:
        log.warning("instagram send failed: %s %s", r.status_code, r.text[:800])
        raise InstagramAPIError(
            "Instagram send message failed",
            status=r.status_code,
            body=r.text[:2000],
        )
    try:
        payload = r.json()
    except Exception as e:
        raise InstagramAPIError("Instagram send response is not JSON") from e
    if not isinstance(payload, dict):
        return None
    mid = payload.get("message_id")
    return str(mid).strip() if mid else None


async def download_instagram_media(url: str) -> tuple[bytes, str] | None:
    u = (url or "").strip()
    if not u:
        return None
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        r = await client.get(u)
    if r.status_code >= 400 or not r.content:
        return None
    ct = (r.headers.get("content-type") or "image/jpeg").split(";")[0].strip()
    if not ct.startswith("image/"):
        ct = "image/jpeg"
    return r.content, ct


async def fetch_instagram_user_profile(
    access_token: str,
    instagram_scoped_user_id: str,
    *,
    fields: str = "name,username,profile_pic",
) -> dict[str, Any] | None:
    """User Profile API: IGSID из webhook → name / @username."""
    token = (access_token or "").strip()
    igsid = (instagram_scoped_user_id or "").strip()
    if not token or not igsid:
        return None
    ver = _graph_version()
    params = {
        "fields": fields,
        "access_token": token,
    }
    url = f"https://graph.instagram.com/v{ver}/{igsid}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, params=params)
    if r.status_code >= 400:
        log.warning(
            "instagram user profile failed igsid=%s status=%s %s",
            igsid[:16],
            r.status_code,
            r.text[:400],
        )
        return None
    try:
        payload = r.json()
    except Exception as e:
        log.warning("instagram user profile not json igsid=%s: %s", igsid[:16], e)
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("error"):
        log.warning(
            "instagram user profile error igsid=%s: %s",
            igsid[:16],
            payload.get("error"),
        )
        return None
    return payload
