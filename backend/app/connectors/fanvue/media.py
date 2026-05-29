"""Fanvue: медиа в чатах — скачивание и загрузка изображений."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.connectors.fanvue.client import FanvueAPIError

log = logging.getLogger(__name__)

CHUNK_SIZE = 8 * 1024 * 1024


def _headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token.strip()}",
        "X-Fanvue-API-Version": settings.fanvue_api_version,
    }


def _base_url() -> str:
    return (settings.fanvue_api_base or "https://api.fanvue.com").rstrip("/")


def fanvue_message_media_uuids(msg: dict[str, Any]) -> list[str]:
    uuids: list[str] = []
    for key in ("mediaUuids", "media_uuids"):
        raw = msg.get(key)
        if isinstance(raw, list):
            for x in raw:
                if isinstance(x, str) and x.strip():
                    uuids.append(x.strip())
                elif isinstance(x, dict) and x.get("uuid"):
                    uuids.append(str(x["uuid"]).strip())
    media = msg.get("media")
    if isinstance(media, list):
        for item in media:
            if isinstance(item, dict):
                u = item.get("uuid") or item.get("mediaUuid")
                if u:
                    uuids.append(str(u).strip())
    seen: set[str] = set()
    out: list[str] = []
    for u in uuids:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out[:5]


async def fanvue_fetch_message_image_bytes(
    access_token: str,
    *,
    fan_user_uuid: str,
    message_uuid: str,
    media_uuids: list[str],
) -> tuple[bytes, str] | None:
    if not message_uuid or not media_uuids:
        return None
    base = _base_url()
    params = {
        "mediaUuids": ",".join(media_uuids[:5]),
        "variants": "main,thumbnail",
    }
    url = f"{base}/chats/{fan_user_uuid}/messages/{message_uuid}/media"
    async with httpx.AsyncClient(timeout=90.0) as client:
        r = await client.get(url, headers=_headers(access_token), params=params)
    if r.status_code >= 400:
        log.warning("fanvue fetch message media %s: %s %s", message_uuid, r.status_code, r.text[:400])
        return None
    try:
        data = r.json()
    except Exception:
        return None
    items = data if isinstance(data, list) else data.get("data") or data.get("media") or []
    if isinstance(items, dict):
        items = list(items.values())
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        variants = item.get("variants") or []
        if isinstance(variants, list):
            for v in variants:
                if not isinstance(v, dict):
                    continue
                vtype = str(v.get("variantType") or v.get("type") or "").lower()
                dl = (v.get("url") or "").strip()
                if dl and vtype in ("main", "thumbnail", "thumbnail_gallery", ""):
                    return await _download_url(dl)
        dl = (item.get("url") or "").strip()
        if dl:
            return await _download_url(dl)
    return None


async def _download_url(url: str) -> tuple[bytes, str] | None:
    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            r = await client.get(url)
        if r.status_code >= 400:
            return None
        ct = (r.headers.get("content-type") or "image/jpeg").split(";")[0].strip()
        if not ct.startswith("image/"):
            ct = "image/jpeg"
        return r.content, ct
    except Exception as e:
        log.warning("fanvue media download failed: %s", e)
        return None


async def fanvue_upload_image_bytes(
    access_token: str,
    *,
    filename: str,
    raw: bytes,
    content_type: str,
) -> str:
    """Загрузка изображения в vault Fanvue; возвращает mediaUuid."""
    if not raw:
        raise FanvueAPIError(400, "empty image")
    base = _base_url()
    name = (filename or "image.jpg").strip() or "image.jpg"
    ct = (content_type or "image/jpeg").split(";")[0].strip() or "image/jpeg"

    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{base}/media/uploads",
            headers={**_headers(access_token), "Content-Type": "application/json"},
            json={"name": name, "filename": name, "mediaType": "image"},
        )
        if r.status_code >= 400:
            raise FanvueAPIError(r.status_code, r.text)
        init = r.json()
        media_uuid = str(init.get("mediaUuid") or init.get("uuid") or "").strip()
        upload_id = str(init.get("uploadId") or init.get("upload_id") or "").strip()
        if not media_uuid or not upload_id:
            raise FanvueAPIError(502, f"fanvue upload init invalid: {r.text[:500]}")

        part_num = 1
        r_part = await client.get(
            f"{base}/media/uploads/{upload_id}/parts/{part_num}",
            headers=_headers(access_token),
        )
        if r_part.status_code >= 400:
            raise FanvueAPIError(r_part.status_code, r_part.text)
        part_body = r_part.json()
        signed_url = str(part_body.get("url") or part_body.get("signedUrl") or "").strip()
        if not signed_url:
            raise FanvueAPIError(502, "fanvue part url missing")

        put_headers = {"Content-Type": ct}
        r_put = await client.put(signed_url, content=raw, headers=put_headers)
        if r_put.status_code >= 400:
            raise FanvueAPIError(r_put.status_code, r_put.text[:500])
        etag = (r_put.headers.get("etag") or r_put.headers.get("ETag") or "").strip().strip('"')

        r_done = await client.post(
            f"{base}/media/uploads/{upload_id}/complete",
            headers={**_headers(access_token), "Content-Type": "application/json"},
            json={"parts": [{"partNumber": part_num, "ETag": etag or "etag"}]},
        )
        if r_done.status_code >= 400:
            raise FanvueAPIError(r_done.status_code, r_done.text)

    return media_uuid
