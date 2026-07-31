"""Скачивание медиа из Telethon-сообщений (стикеры, GIF, фото)."""

from __future__ import annotations

import logging

from telethon.tl.types import DocumentAttributeSticker, Message as TlMessage

log = logging.getLogger(__name__)

_TGS_MIME = "application/x-tgs"


def sticker_alt_text(message: TlMessage) -> str | None:
    doc = message.document
    if not doc:
        return None
    for attr in doc.attributes or []:
        if isinstance(attr, DocumentAttributeSticker):
            alt = (attr.alt or "").strip()
            return alt or "🎭"
    return None


def _resolve_mime(message: TlMessage) -> str | None:
    if message.photo:
        return "image/jpeg"
    if message.sticker:
        doc = message.document
        mime = ((doc.mime_type if doc else None) or "image/webp").split(";")[0].strip().lower()
        if mime == _TGS_MIME:
            return None
        return mime or "image/webp"
    if getattr(message, "gif", False):
        return "video/mp4"
    if message.video:
        doc = message.video
        return ((doc.mime_type if doc else None) or "video/mp4").split(";")[0].strip().lower()
    if message.document:
        doc = message.document
        mime = (doc.mime_type or "").split(";")[0].strip().lower()
        if not mime:
            return None
        if mime == _TGS_MIME:
            return None
        if mime.startswith("image/") or mime.startswith("video/"):
            return mime
    return None


async def download_telegram_user_media(
    message: TlMessage,
    client,
) -> tuple[bytes, str] | None:
    mime = _resolve_mime(message)
    if not mime or client is None:
        return None
    try:
        raw = await client.download_media(message, bytes)
        if not raw:
            return None
        return raw, mime
    except Exception:
        log.exception("telegram_user media download failed msg=%s", message.id)
        return None
