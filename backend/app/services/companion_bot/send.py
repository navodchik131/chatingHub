"""Отправка ответа компаньона на платформу и сохранение в БД."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message, MessageDirection, Platform
from app.db.repo import add_message, mark_conversation_read
from app.services.chat_messages import message_to_out
from app.services.chat_message_meta import platform_message_id_from_meta
from app.services.chat_outbound import send_fanvue_outbound, send_telegram_outbound
from app.services.crypto_secret import decrypt_secret
from app.services.platform_connections import (
    resolve_fanvue_connection_for_conversation,
    resolve_telegram_connection_for_conversation,
)
from app.services.realtime import hub
from app.services.translation import translate_to_russian

log = logging.getLogger(__name__)


async def send_companion_outbound(
    session: AsyncSession,
    *,
    owner_id: int,
    conv: Conversation,
    text: str,
    reply_to_message_id: int | None,
    bot_response_event_id: int,
    sender_user_id: int | None = None,
) -> Message:
    outgoing = (text or "").strip()
    if not outgoing:
        raise ValueError("empty outbound text")

    platform_message_id: str | None = None
    reply_target: Message | None = None
    if reply_to_message_id:
        reply_target = await session.get(Message, reply_to_message_id)

    if conv.platform == Platform.telegram:
        row_tg = await resolve_telegram_connection_for_conversation(session, conv, owner_id)
        if not row_tg:
            raise RuntimeError("telegram connection missing")
        token = decrypt_secret(row_tg.bot_token_encrypted)
        tid = int(conv.external_topic_id)
        cid = int(conv.external_chat_id)
        tg_reply_id: int | None = None
        if reply_target:
            if reply_target.platform_message_id:
                try:
                    tg_reply_id = int(reply_target.platform_message_id)
                except ValueError:
                    tg_reply_id = None
            if tg_reply_id is None:
                raw = platform_message_id_from_meta(reply_target.meta)
                if raw:
                    try:
                        tg_reply_id = int(raw)
                    except ValueError:
                        tg_reply_id = None
        sent_id = await send_telegram_outbound(
            token=token,
            chat_id=cid,
            topic_id=tid,
            text=outgoing,
            image_bytes=None,
            image_mime=None,
            reply_to_telegram_message_id=tg_reply_id,
        )
        if sent_id is not None:
            platform_message_id = str(sent_id)
    elif conv.platform == Platform.fanvue:
        row_fv = await resolve_fanvue_connection_for_conversation(session, conv, owner_id)
        if not row_fv:
            raise RuntimeError("fanvue connection missing")
        from app.services.fanvue_connection import ensure_fanvue_access_token

        fv_tok = await ensure_fanvue_access_token(session, row_fv)
        fv_reply_uuid = None
        if reply_target:
            fv_reply_uuid = reply_target.platform_message_id or platform_message_id_from_meta(
                reply_target.meta
            )
        platform_message_id = await send_fanvue_outbound(
            access_token=fv_tok,
            fan_uuid=conv.external_chat_id,
            text=outgoing,
            image_bytes=None,
            image_mime=None,
            reply_to_message_uuid=fv_reply_uuid,
        )
    else:
        raise RuntimeError(f"companion bot unsupported platform: {conv.platform.value}")

    stored_original = outgoing
    stored_translated: str | None = outgoing
    try:
        ru_text, _src = await translate_to_russian(outgoing)
        if ru_text.strip():
            stored_original = ru_text.strip()
    except Exception as e:
        log.warning("companion outbound ru translate failed: %s", e)

    meta = json.dumps(
        {
            "companion_bot": True,
            "bot_response_event_id": bot_response_event_id,
        },
        ensure_ascii=False,
    )
    conv.updated_at = datetime.now(timezone.utc)
    row = await add_message(
        session,
        conv.id,
        MessageDirection.outbound,
        stored_original,
        stored_translated,
        meta=meta,
        reply_to_message_id=reply_to_message_id,
        platform_message_id=platform_message_id,
        sender_user_id=sender_user_id,
    )
    await mark_conversation_read(session, conv.id, owner_id)
    await session.flush()
    await session.refresh(row, attribute_names=["attachments"])
    return row


async def broadcast_companion_message(
    *,
    owner_id: int,
    conv_id: int,
    row: Message,
) -> None:
    out = message_to_out(row, owner_id=owner_id)
    await hub.broadcast_user(
        owner_id,
        {
            "type": "new_message",
            "conversation_id": conv_id,
            "message": out.model_dump(mode="json"),
        },
    )
