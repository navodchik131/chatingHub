"""Приём личных сообщений через MTProto."""

from __future__ import annotations

import asyncio
import json
import logging

from sqlalchemy import select
from telethon.tl.types import Message as TlMessage
from telethon.tl.types import PeerUser
from telethon.tl.types import User as TlUser

from app.connectors.telegram_user.media import download_telegram_user_media, sticker_alt_text
from app.db.models import Conversation, Message, MessageDirection, Platform
from app.db.repo import get_or_create_conversation, get_user_with_billing
from app.db.session import SessionLocal
from app.services.chat_ingest import persist_inbound_chat_message
from app.services.chat_messages import message_to_out
from app.services.companion_bot.schedule import schedule_companion_reply
from app.services.realtime import hub
from app.services.translation import translate_to_russian

log = logging.getLogger(__name__)


async def _defer_inbound_translation(
    *,
    owner_user_id: int,
    conv_id: int,
    message_id: int,
    text: str,
) -> None:
    """Перевод после broadcast — сообщение видно в Unibox сразу с оригиналом."""
    try:
        translated, src_lang = await asyncio.wait_for(translate_to_russian(text), timeout=15.0)
    except Exception:
        log.warning("telegram_user deferred translate failed msg=%s", message_id)
        return
    async with SessionLocal() as session:
        row = await session.get(Message, message_id)
        conv = await session.get(Conversation, conv_id)
        if not row or not conv:
            return
        row.text_translated = translated or None
        if src_lang and src_lang != "unknown":
            conv.user_lang = src_lang
        await session.commit()
        await session.refresh(row)
        await session.refresh(row, attribute_names=["attachments"])
        payload = message_to_out(row, owner_id=owner_user_id).model_dump(mode="json")
    await hub.broadcast_user(
        owner_user_id,
        {"type": "message_updated", "conversation_id": conv_id, "message": payload},
    )


def _display_name(user: TlUser | None) -> str:
    if not user:
        return "Telegram user"
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(p for p in parts if p).strip()
    if name:
        return name
    if user.username:
        return f"@{user.username}"
    return f"user_{user.id}"


def _message_text(msg: TlMessage) -> str:
    return (msg.message or "").strip()


def _has_media(msg: TlMessage) -> bool:
    return bool(msg.photo or msg.document or msg.sticker or msg.video or msg.gif)


async def ingest_telegram_user_dm(
    *,
    owner_user_id: int,
    session_row_id: int,
    studio_model_id: int | None,
    message: TlMessage,
    sender: TlUser | None,
    client,
    source: str = "mtproto",
) -> None:
    if message.out:
        return
    if not isinstance(message.peer_id, PeerUser):
        return

    text = _message_text(message)
    has_media = _has_media(message)
    if not text and not has_media:
        return

    peer_id: int | None = None
    if sender is not None:
        peer_id = int(sender.id)
    elif isinstance(message.peer_id, PeerUser):
        peer_id = int(message.peer_id.user_id)
    if peer_id is None:
        return
    chat_id = str(peer_id)
    topic_id = "0"
    display = _display_name(sender)

    image_bytes: bytes | None = None
    image_mime: str | None = None
    attachment_kind = None
    from app.db.models import MessageAttachmentKind

    if has_media and client is not None:
        try:
            media = await asyncio.wait_for(
                download_telegram_user_media(message, client),
                timeout=12.0,
            )
        except asyncio.TimeoutError:
            log.warning("telegram_user media download timeout msg=%s", message.id)
            media = None
        if media:
            image_bytes, image_mime, is_video_note = media
            if is_video_note:
                attachment_kind = MessageAttachmentKind.video_note
        elif message.sticker and not text:
            text = sticker_alt_text(message) or "🎭"

    if not text and not image_bytes:
        return

    defer_translate = False
    async with SessionLocal() as session:
        user = await get_user_with_billing(session, owner_user_id)
        if not user:
            log.warning("telegram_user ingest: user %s not found", owner_user_id)
            return

        conv = await get_or_create_conversation(
            session,
            owner_user_id,
            Platform.telegram_user,
            chat_id,
            topic_id,
            display,
            telegram_user_session_id=session_row_id,
            studio_model_id=studio_model_id,
        )

        defer_translate = bool(text and not conv.auto_translate_disabled)
        translated, src_lang = "", None

        reply_to_message_id: int | None = None
        if message.reply_to and getattr(message.reply_to, "reply_to_msg_id", None):
            parent = await session.scalar(
                select(Message).where(
                    Message.conversation_id == conv.id,
                    Message.platform_message_id == str(message.reply_to.reply_to_msg_id),
                )
            )
            if parent:
                reply_to_message_id = parent.id

        # access_hash нужен для исходящих при ephemeral MTProto (StringSession без entity cache)
        peer_access_hash = int(sender.access_hash) if sender and sender.access_hash else None
        if sender and client is not None:
            try:
                await client.get_input_entity(sender)
            except Exception:
                pass

        meta = json.dumps(
            {
                "message_id": message.id,
                "from_user_id": peer_id,
                "from_user_access_hash": peer_access_hash,
                "ingest_source": source,
                "has_image": bool(image_bytes),
                "has_media": bool(image_bytes),
                "media_mime": image_mime,
                "telegram_route": "personal",
            },
            ensure_ascii=False,
        )
        conv_id, payload = await persist_inbound_chat_message(
            session,
            owner_user_id=owner_user_id,
            conv=conv,
            display=display,
            text_original=text,
            text_translated=translated if translated else None,
            src_lang=src_lang,
            meta=meta,
            image_bytes=image_bytes,
            image_mime=image_mime,
            attachment_kind=attachment_kind,
            reply_to_message_id=reply_to_message_id,
            platform_message_id=str(message.id),
        )
        if payload is None:
            return
        trigger_message_id = int(payload["id"])
        await session.commit()

    if defer_translate:
        asyncio.create_task(
            _defer_inbound_translation(
                owner_user_id=owner_user_id,
                conv_id=conv_id,
                message_id=trigger_message_id,
                text=text,
            )
        )

    schedule_companion_reply(
        owner_user_id=owner_user_id,
        conv_id=conv_id,
        trigger_message_id=trigger_message_id,
    )

    log.info(
        "ingested telegram_user DM user=%s conv=%s peer=%s source=%s media=%s",
        owner_user_id,
        conv_id,
        peer_id,
        source,
        image_mime if image_bytes else None,
    )
