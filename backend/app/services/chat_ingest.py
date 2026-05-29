"""Общая логика приёма входящего сообщения чата (текст + опционально фото)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message, MessageDirection
from app.db.repo import add_message
from app.schemas import MessageOut
from app.services.chat_attachment import save_chat_image_bytes
from app.services.chat_messages import add_message_attachment, message_to_out
from app.services.realtime import hub
from app.services.webpush import notify_inbound_message

log = logging.getLogger(__name__)


async def persist_inbound_chat_message(
    session: AsyncSession,
    *,
    owner_user_id: int,
    conv: Conversation,
    display: str,
    text_original: str,
    text_translated: str | None,
    src_lang: str | None,
    meta: str | None,
    image_bytes: bytes | None = None,
    image_mime: str | None = None,
) -> tuple[int, dict]:
    if src_lang and not conv.user_lang:
        conv.user_lang = src_lang
    elif src_lang and src_lang != "unknown":
        conv.user_lang = src_lang
    conv.updated_at = datetime.now(timezone.utc)

    row = await add_message(
        session,
        conv.id,
        MessageDirection.inbound,
        text_original or "",
        text_translated,
        meta=meta,
    )
    if image_bytes:
        try:
            rel, mime = save_chat_image_bytes(
                owner_id=owner_user_id,
                raw=image_bytes,
                content_type=image_mime,
            )
            await add_message_attachment(
                session,
                message_id=row.id,
                relative_path=rel,
                mime_type=mime,
            )
        except ValueError as e:
            log.warning("chat inbound image save failed: %s", e)

    await session.flush()
    await session.refresh(row)
    await session.refresh(row, attribute_names=["attachments"])
    conv_id = conv.id
    payload = message_to_out(row, owner_id=owner_user_id).model_dump(mode="json")

    await hub.broadcast_user(
        owner_user_id,
        {
            "type": "new_message",
            "conversation_id": conv_id,
            "message": payload,
        },
    )
    preview = (text_translated or text_original or "").strip()
    if not preview and image_bytes:
        preview = "📷 Изображение"
    else:
        preview = preview[:200]
    await notify_inbound_message(
        owner_user_id,
        conversation_id=conv_id,
        title=f"{display} · {conv.platform.value}",
        body=preview or "Новое сообщение",
    )
    return conv_id, payload
