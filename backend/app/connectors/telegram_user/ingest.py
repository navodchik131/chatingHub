"""Приём личных сообщений через MTProto."""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from telethon.tl.types import Message as TlMessage
from telethon.tl.types import PeerUser
from telethon.tl.types import User as TlUser

from app.db.models import Conversation, Message, MessageDirection, Platform
from app.db.repo import get_or_create_conversation, get_user_with_billing
from app.db.session import SessionLocal
from app.services.chat_ingest import persist_inbound_chat_message
from app.services.companion_bot.schedule import schedule_companion_reply
from app.services.translation import translate_to_russian

log = logging.getLogger(__name__)


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
    if not message.is_private:
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
    if has_media and client is not None:
        try:
            raw = await client.download_media(message, bytes)
            if raw:
                image_bytes = raw
                if message.photo:
                    image_mime = "image/jpeg"
                elif message.document and message.document.mime_type:
                    image_mime = message.document.mime_type
                else:
                    image_mime = "application/octet-stream"
        except Exception:
            log.exception("telegram_user ingest: media download failed msg=%s", message.id)

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

        if text and not conv.auto_translate_disabled:
            translated, src_lang = await translate_to_russian(text)
        else:
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

        meta = json.dumps(
            {
                "message_id": message.id,
                "from_user_id": peer_id,
                "ingest_source": source,
                "has_image": bool(image_bytes),
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
            text_translated=translated if text and not conv.auto_translate_disabled else None,
            src_lang=src_lang,
            meta=meta,
            image_bytes=image_bytes,
            image_mime=image_mime,
            reply_to_message_id=reply_to_message_id,
            platform_message_id=str(message.id),
        )
        if payload is None:
            return
        trigger_message_id = int(payload["id"])
        await session.commit()

    schedule_companion_reply(
        owner_user_id=owner_user_id,
        conv_id=conv_id,
        trigger_message_id=trigger_message_id,
    )

    log.info(
        "ingested telegram_user DM user=%s conv=%s peer=%s source=%s image=%s",
        owner_user_id,
        conv_id,
        peer_id,
        source,
        bool(image_bytes),
    )
