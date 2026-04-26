"""Приём вебхуков Fanvue и запись в БД (мультитенант)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message, MessageDirection, Platform
from app.db.repo import add_message, get_or_create_conversation, get_user_with_billing
from app.schemas import MessageOut
from app.services.realtime import hub
from app.services.translation import translate_to_russian
from app.services.webpush import notify_inbound_message

log = logging.getLogger(__name__)


def _meta_needle_fanvue_message_uuid(message_uuid: str) -> str:
    return f'"fanvue_message_uuid": "{message_uuid}"'


async def _fanvue_inbound_exists(
    session: AsyncSession, owner_user_id: int, message_uuid: str
) -> bool:
    if not message_uuid:
        return False
    needle = _meta_needle_fanvue_message_uuid(message_uuid)
    n = await session.scalar(
        select(func.count())
        .select_from(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Message.direction == MessageDirection.inbound,
            Message.meta.contains(needle),
            Conversation.user_id == owner_user_id,
        )
    )
    return int(n or 0) > 0


async def ingest_fanvue_message_received(
    session: AsyncSession,
    body: dict[str, Any],
    owner_user_id: int,
) -> dict[str, Any]:
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

    if message_uuid and await _fanvue_inbound_exists(session, owner_user_id, message_uuid):
        log.debug("fanvue duplicate webhook message %s", message_uuid)
        return {"ok": True, "skipped": "duplicate"}

    user = await get_user_with_billing(session, owner_user_id)
    if not user:
        raise ValueError("user not found")

    display = sender.get("displayName") or sender.get("handle") or fan_uuid
    if not isinstance(display, str):
        display = str(display)

    translated, src_lang = await translate_to_russian(text_s)

    conv = await get_or_create_conversation(
        session,
        owner_user_id,
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

    await hub.broadcast_user(
        owner_user_id,
        {
            "type": "new_message",
            "conversation_id": conv.id,
            "message": MessageOut.model_validate(row).model_dump(mode="json"),
        },
    )
    preview = (translated or text_s)[:200]
    await notify_inbound_message(
        owner_user_id,
        conversation_id=conv.id,
        title=f"{display} · Fanvue",
        body=preview,
    )
    log.info("ingested fanvue DM user=%s conv=%s fan=%s", owner_user_id, conv.id, fan_uuid)
    return {"ok": True, "conversation_id": conv.id, "message_id": row.id}


def is_fanvue_message_read_payload(body: dict[str, Any]) -> bool:
    return (
        "counterpartUuid" in body
        and "readMessagesCount" in body
        and "recipientUuid" in body
    )
