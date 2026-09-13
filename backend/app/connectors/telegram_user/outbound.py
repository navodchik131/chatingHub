"""Исходящие сообщения через MTProto."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import (
    ChatWriteForbiddenError,
    FloodWaitError,
    InputUserDeactivatedError,
    PeerIdInvalidError,
    UserIsBlockedError,
)

from app.connectors.telegram_user.peer_entity import resolve_telegram_user_peer
from app.connectors.telegram_user.session_runtime import run_with_telegram_user_client
from app.services.telegram_video_note import convert_video_bytes_to_telegram_note_async
from fastapi import HTTPException

log = logging.getLogger(__name__)


def _telegram_user_send_http_error(exc: BaseException) -> HTTPException:
    """MTProto-ошибки отправки → 502 с текстом для оператора (не голый 500)."""
    if isinstance(exc, UserIsBlockedError):
        return HTTPException(
            status_code=502,
            detail="Пользователь заблокировал ваш Telegram — отправка невозможна.",
        )
    if isinstance(exc, ChatWriteForbiddenError):
        return HTTPException(
            status_code=502,
            detail="Telegram запретил писать этому пользователю (ЧС или закрытые сообщения).",
        )
    if isinstance(exc, InputUserDeactivatedError):
        return HTTPException(
            status_code=410,
            detail="Аккаунт Telegram пользователя удалён или недоступен.",
        )
    if isinstance(exc, PeerIdInvalidError):
        return HTTPException(
            status_code=502,
            detail="Telegram не находит этого пользователя — проверьте диалог.",
        )
    if isinstance(exc, FloodWaitError):
        sec = int(getattr(exc, "seconds", 0) or 0)
        return HTTPException(
            status_code=429,
            detail=f"Telegram просит подождать {sec} сек. перед следующей отправкой.",
        )
    if isinstance(exc, RuntimeError) and "not authorized" in str(exc).lower():
        return HTTPException(
            status_code=503,
            detail="Личный Telegram отключён — переподключите в «Подключения».",
        )
    msg = str(exc).strip() or exc.__class__.__name__
    if "could not find the input entity" in msg.lower():
        return HTTPException(
            status_code=502,
            detail=(
                "Telegram не знает этого пользователя в текущей сессии. "
                "Попросите его написать снова или переподключите личный Telegram."
            ),
        )
    return HTTPException(status_code=502, detail=f"Telegram: {msg[:480]}")


async def _send_via_client(
    client: TelegramClient,
    *,
    peer_user_id: int,
    peer_username: str | None = None,
    peer_access_hash: int | None = None,
    text: str,
    image_bytes: bytes | None,
    image_mime: str | None,
    video_bytes: bytes | None,
    video_mime: str | None,
    send_as_video_note: bool = False,
    video_note_already_converted: bool = False,
    reply_to_telegram_message_id: int | None,
) -> int | None:
    peer = await resolve_telegram_user_peer(
        client,
        peer_user_id,
        username=peer_username,
        access_hash=peer_access_hash,
    )
    reply_to = reply_to_telegram_message_id if reply_to_telegram_message_id else None
    sent = None
    if video_bytes:
        payload = video_bytes
        if send_as_video_note and not video_note_already_converted:
            try:
                payload = await convert_video_bytes_to_telegram_note_async(
                    video_bytes,
                    mime_hint=video_mime,
                )
            except (RuntimeError, ValueError) as exc:
                raise HTTPException(status_code=502, detail=str(exc)[:500]) from exc
        ext = ".mp4" if send_as_video_note else ".mp4"
        if not send_as_video_note and video_mime and "webm" in video_mime:
            ext = ".webm"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(payload)
            tmp_path = tmp.name
        try:
            if send_as_video_note:
                sent = await client.send_file(
                    peer,
                    tmp_path,
                    reply_to=reply_to,
                    video_note=True,
                )
                if (text or "").strip():
                    await client.send_message(peer, text, reply_to=reply_to)
            elif (text or "").strip():
                sent = await client.send_file(
                    peer,
                    tmp_path,
                    caption=text,
                    reply_to=reply_to,
                    force_document=False,
                )
            else:
                sent = await client.send_file(
                    peer,
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
                    peer,
                    tmp_path,
                    caption=text,
                    reply_to=reply_to,
                )
            else:
                sent = await client.send_file(
                    peer,
                    tmp_path,
                    reply_to=reply_to,
                )
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    elif (text or "").strip():
        sent = await client.send_message(peer, text, reply_to=reply_to)
    else:
        raise ValueError("empty outbound message")
    return int(sent.id) if sent and sent.id else None


async def send_telegram_user_outbound(
    *,
    session_id: int,
    session_encrypted: str,
    peer_user_id: int,
    peer_username: str | None = None,
    peer_access_hash: int | None = None,
    text: str,
    image_bytes: bytes | None = None,
    image_mime: str | None = None,
    video_bytes: bytes | None = None,
    video_mime: str | None = None,
    send_as_video_note: bool = False,
    video_note_already_converted: bool = False,
    reply_to_telegram_message_id: int | None = None,
) -> int | None:
    try:
        return await run_with_telegram_user_client(
            session_id=session_id,
            session_encrypted=session_encrypted,
            operation=lambda client: _send_via_client(
                client,
                peer_user_id=peer_user_id,
                peer_username=peer_username,
                peer_access_hash=peer_access_hash,
                text=text,
                image_bytes=image_bytes,
                image_mime=image_mime,
                video_bytes=video_bytes,
                video_mime=video_mime,
                send_as_video_note=send_as_video_note,
                video_note_already_converted=video_note_already_converted,
                reply_to_telegram_message_id=reply_to_telegram_message_id,
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.warning(
            "telegram_user outbound failed peer=%s: %s",
            peer_user_id,
            exc,
            exc_info=True,
        )
        raise _telegram_user_send_http_error(exc) from exc


async def set_telegram_user_message_reaction(
    *,
    session_id: int,
    session_encrypted: str,
    peer_user_id: int,
    telegram_message_id: int,
    emoji: str | None,
) -> bool:
    """emoji=None — снять реакцию. True если Telegram принял."""
    from telethon.tl.functions.messages import SendReactionRequest
    from telethon.tl.types import ReactionEmoji

    async def _op(client: TelegramClient) -> bool:
        reactions = []
        if emoji and emoji.strip():
            reactions = [ReactionEmoji(emoticon=emoji.strip())]
        await client(
            SendReactionRequest(
                peer=peer_user_id,
                msg_id=int(telegram_message_id),
                reaction=reactions,
            )
        )
        return True

    try:
        return await run_with_telegram_user_client(
            session_id=session_id,
            session_encrypted=session_encrypted,
            operation=_op,
        )
    except Exception:
        log.exception(
            "telegram_user set reaction failed peer=%s msg=%s emoji=%s",
            peer_user_id,
            telegram_message_id,
            emoji,
        )
        return False


async def download_telegram_user_avatar(
    *,
    session_id: int,
    session_encrypted: str,
    peer_user_id: int,
) -> tuple[bytes, str] | None:
    async def _op(client: TelegramClient) -> tuple[bytes, str] | None:
        photos = await client.get_profile_photos(peer_user_id, limit=1)
        if not photos:
            return None
        raw = await client.download_media(photos[0], bytes)
        if not raw:
            return None
        return raw, "image/jpeg"

    try:
        return await run_with_telegram_user_client(
            session_id=session_id,
            session_encrypted=session_encrypted,
            operation=_op,
        )
    except Exception:
        log.exception("telegram_user avatar download failed peer=%s", peer_user_id)
        return None
