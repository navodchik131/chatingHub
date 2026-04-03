"""Приём вебхуков Fanvue и запись в БД."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message, MessageDirection, Platform
from app.db.repo import add_message, get_or_create_conversation
from app.schemas import MessageOut
from app.services.realtime import hub
from app.services.translation import translate_to_russian

log = logging.getLogger(__name__)


def _meta_needle_fanvue_message_uuid(message_uuid: str) -> str:
    return f'"fanvue_message_uuid": "{message_uuid}"'


async def _fanvue_inbound_exists(session: AsyncSession, message_uuid: str) -> bool:
    if not message_uuid:
        return False
    needle = _meta_needle_fanvue_message_uuid(message_uuid)
    n = await session.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.direction == MessageDirection.inbound,
            Message.meta.contains(needle),
        )
    )
    return int(n or 0) > 0


async def ingest_fanvue_message_received(
    session: AsyncSession,
    body: dict[str, Any],
) -> dict[str, Any]:
    """
    Обрабатывает payload вебхука «новое сообщение» (см. Message Received в доке Fanvue).
    """
    msg = body.get("message") or {}
    sender = body.get("sender") or {}
    recipient_uuid = body.get("recipientUuid")
    if not isinstance(msg, dict) or not isinstance(sender, dict):
        raise ValueError("invalid message/sender shape")

    message_uuid = str(msg.get("uuid") or body.get("messageUuid") or "").strip()
    text = msg.get("text")
    text_s = (text if isinstance(text, str) else "") or ""
    text_s = text_s.strip()
    has_media = bool(msg.get("hasMedia"))

    if not text_s:
        if has_media:
            log.info("fanvue webhook: skip inbound with media only (no text) uuid=%s", message_uuid)
            return {"ok": True, "skipped": "media_only"}
        log.info("fanvue webhook: empty text uuid=%s", message_uuid)
        return {"ok": True, "skipped": "empty"}

    fan_uuid = str(sender.get("uuid") or "").strip()
    if not fan_uuid:
        raise ValueError("missing sender.uuid")

    creator_uuid = str(recipient_uuid or "").strip() or "default"

    if message_uuid and await _fanvue_inbound_exists(session, message_uuid):
        log.debug("fanvue duplicate webhook message %s", message_uuid)
        return {"ok": True, "skipped": "duplicate"}

    display = sender.get("displayName") or sender.get("handle") or fan_uuid
    if not isinstance(display, str):
        display = str(display)

    translated, src_lang = await translate_to_russian(text_s)

    conv = await get_or_create_conversation(
        session,
        Platform.fanvue,
        fan_uuid,
        creator_uuid,
        display,
    )
    if not conv.user_lang:
        conv.user_lang = src_lang
    elif src_lang and src_lang != "unknown":
        conv.user_lang = src_lang
    conv.updated_at = datetime.now(timezone.utc)

    meta_obj: dict[str, Any] = {
        "fanvue_message_uuid": message_uuid or None,
        "sender_uuid": fan_uuid,
        "recipient_uuid": creator_uuid,
        "ingest": "fanvue.message.received",
    }
    meta = json.dumps(meta_obj, ensure_ascii=False)

    row = await add_message(
        session,
        conv.id,
        MessageDirection.inbound,
        text_s,
        translated,
        meta=meta,
    )
    await session.commit()
    await session.refresh(row)

    await hub.broadcast(
        {
            "type": "new_message",
            "conversation_id": conv.id,
            "message": MessageOut.model_validate(row).model_dump(mode="json"),
        }
    )
    log.info("ingested fanvue DM conv=%s fan=%s", conv.id, fan_uuid)
    return {"ok": True, "conversation_id": conv.id, "message_id": row.id}


def is_fanvue_message_read_payload(body: dict[str, Any]) -> bool:
    return (
        "counterpartUuid" in body
        and "readMessagesCount" in body
        and "recipientUuid" in body
    )
