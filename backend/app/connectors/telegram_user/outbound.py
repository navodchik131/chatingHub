"""Исходящие сообщения через MTProto."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from telethon import TelegramClient

from app.connectors.telegram_user.client import build_telegram_client

log = logging.getLogger(__name__)


async def send_telegram_user_outbound(
    *,
    session_encrypted: str,
    peer_user_id: int,
    text: str,
    image_bytes: bytes | None = None,
    image_mime: str | None = None,
    video_bytes: bytes | None = None,
    video_mime: str | None = None,
    reply_to_telegram_message_id: int | None = None,
) -> int | None:
    client = build_telegram_client(session_encrypted=session_encrypted)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("telegram user session not authorized")
        reply_to = reply_to_telegram_message_id if reply_to_telegram_message_id else None
        sent = None
        if video_bytes:
            ext = ".mp4"
            if video_mime and "webm" in video_mime:
                ext = ".webm"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(video_bytes)
                tmp_path = tmp.name
            try:
                if (text or "").strip():
                    sent = await client.send_file(
                        peer_user_id,
                        tmp_path,
                        caption=text,
                        reply_to=reply_to,
                        force_document=False,
                    )
                else:
                    sent = await client.send_file(
                        peer_user_id,
                        tmp_path,
                        reply_to=reply_to,
                        force_document=False,
                    )
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        elif image_bytes:
            ext = ".jpg"
            if image_mime and "png" in image_mime:
                ext = ".png"
            elif image_mime and "webp" in image_mime:
                ext = ".webp"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name
            try:
                if (text or "").strip():
                    sent = await client.send_file(
                        peer_user_id,
                        tmp_path,
                        caption=text,
                        reply_to=reply_to,
                    )
                else:
                    sent = await client.send_file(
                        peer_user_id,
                        tmp_path,
                        reply_to=reply_to,
                    )
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        elif (text or "").strip():
            sent = await client.send_message(peer_user_id, text, reply_to=reply_to)
        else:
            raise ValueError("empty outbound message")
        return int(sent.id) if sent and sent.id else None
    finally:
        await client.disconnect()


async def download_telegram_user_avatar(
    *,
    session_encrypted: str,
    peer_user_id: int,
) -> tuple[bytes, str] | None:
    client = build_telegram_client(session_encrypted=session_encrypted)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            return None
        photos = await client.get_profile_photos(peer_user_id, limit=1)
        if not photos:
            return None
        raw = await client.download_media(photos[0], bytes)
        if not raw:
            return None
        return raw, "image/jpeg"
    except Exception:
        log.exception("telegram_user avatar download failed peer=%s", peer_user_id)
        return None
    finally:
        await client.disconnect()
