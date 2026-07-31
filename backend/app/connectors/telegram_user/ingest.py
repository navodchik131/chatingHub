"""Приём личных сообщений через MTProto."""

from __future__ import annotations

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
        media = await download_telegram_user_media(message, client)
        if media:
            image_bytes, image_mime, is_video_note = media
            if is_video_note:
                attachment_kind = MessageAttachmentKind.video_note
        elif message.sticker and not text:
            text = sticker_alt_text(message) or "🎭"

    if not text and not image_bytes:
        return

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
            text_translated=translated if text and not conv.auto_translate_disabled else None,
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
