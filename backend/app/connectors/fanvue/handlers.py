"""Обработка вебхуков Fanvue → диалоги в БД."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.fanvue.media import (
    fanvue_fetch_message_image_bytes,
    fanvue_message_media_uuids,
)
from app.db.models import FanvueConnection, Message, Platform
from app.db.repo import get_or_create_conversation, get_user_with_billing
from app.services.chat_ingest import persist_inbound_chat_message
from app.services.translation import translate_to_russian

log = logging.getLogger(__name__)


def _meta_needle_fanvue_message_uuid(message_uuid: str) -> str:
    return f'"fanvue_message_uuid": "{message_uuid}"'


async def fanvue_message_exists(
    session: AsyncSession, owner_user_id: int, message_uuid: str
) -> bool:
    needle = _meta_needle_fanvue_message_uuid(message_uuid)
    stmt = (
        select(Message.id)
        .join(Message.conversation)
        .where(
            Message.conversation.has(user_id=owner_user_id),
            Message.meta.isnot(None),
            Message.meta.contains(needle),
        )
        .limit(1)
    )
    r = await session.scalar(stmt)
    return r is not None


def is_fanvue_message_read_payload(body: dict[str, Any]) -> bool:
    return str(body.get("type") or body.get("event") or "").lower() in (
        "message.read",
        "message_read",
    )


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
    media_uuids = fanvue_message_media_uuids(msg)

    if not text_s and not has_media and not media_uuids:
        log.info("fanvue webhook: empty message uuid=%s", message_uuid)
        return {"ok": True, "skipped": "empty"}

    fan_uuid = str(sender.get("uuid") or "").strip()
    if not fan_uuid:
        raise ValueError("missing sender.uuid")

    creator_uuid = str(recipient_uuid or "").strip() or "default"

    if message_uuid and await fanvue_message_exists(session, owner_user_id, message_uuid):
        log.debug("fanvue duplicate webhook message %s", message_uuid)
        return {"ok": True, "skipped": "duplicate"}

    user = await get_user_with_billing(session, owner_user_id)
    if not user:
        raise ValueError("user not found")

    display = sender.get("displayName") or sender.get("handle") or fan_uuid
    if not isinstance(display, str):
        display = str(display)

    translated, src_lang = await translate_to_russian(text_s) if text_s else ("", None)

    image_bytes: bytes | None = None
    image_mime: str | None = None
    if message_uuid and (has_media or media_uuids):
        row_fv = await session.scalar(
            select(FanvueConnection).where(FanvueConnection.user_id == owner_user_id)
        )
        if row_fv:
            try:
                from app.services.fanvue_connection import ensure_fanvue_access_token

                fv_tok = await ensure_fanvue_access_token(session, row_fv)
                img = await fanvue_fetch_message_image_bytes(
                    fv_tok,
                    fan_user_uuid=fan_uuid,
                    message_uuid=message_uuid,
                    media_uuids=media_uuids or [],
                )
                if img:
                    image_bytes, image_mime = img
            except Exception as e:
                log.warning("fanvue inbound media fetch failed: %s", e)

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
        "has_image": bool(image_bytes),
        "media_uuids": media_uuids,
    }
    meta = json.dumps(meta_obj, ensure_ascii=False)

    await persist_inbound_chat_message(
        session,
        owner_user_id=owner_user_id,
        conv=conv,
        display=display,
        text_original=text_s,
        text_translated=translated if text_s else None,
        src_lang=src_lang,
        meta=meta,
        image_bytes=image_bytes,
        image_mime=image_mime,
    )
    await session.commit()

    return {"ok": True}


async def ingest_fanvue_message_from_api(
    session: AsyncSession,
    *,
    owner_user_id: int,
    creator_uuid: str,
    fan_uuid: str,
    fan_display: str,
    msg: dict[str, Any],
    access_token: str,
    fetch_media: bool = True,
    silent: bool = True,
) -> str:
    """Импорт одного сообщения из GET /chats/.../messages. Возвращает imported|skipped|empty."""
    from app.db.models import MessageDirection
    from app.db.repo import add_message
    from app.services.fanvue_connection import ensure_fanvue_access_token

    message_uuid = str(msg.get("uuid") or "").strip()
    text = msg.get("text")
    text_s = (text if isinstance(text, str) else "") or ""
    text_s = text_s.strip()
    has_media = bool(msg.get("hasMedia"))
    media_uuids = fanvue_message_media_uuids(msg)

    if not text_s and not has_media and not media_uuids:
        return "empty"

    if message_uuid and await fanvue_message_exists(session, owner_user_id, message_uuid):
        return "skipped"

    sender = msg.get("sender") or {}
    sender_uuid = str(sender.get("uuid") or "").strip()
    if not sender_uuid:
        return "empty"

    is_outbound = sender_uuid == creator_uuid.strip()
    if not is_outbound and sender_uuid != fan_uuid.strip():
        return "empty"

    display = fan_display or fan_uuid
    if not isinstance(display, str):
        display = str(display)

    conv = await get_or_create_conversation(
        session,
        owner_user_id,
        Platform.fanvue,
        fan_uuid,
        creator_uuid,
        display,
    )

    meta_obj: dict[str, Any] = {
        "fanvue_message_uuid": message_uuid or None,
        "sender_uuid": sender_uuid,
        "recipient_uuid": creator_uuid if is_outbound else fan_uuid,
        "ingest": "fanvue.history.sync",
        "media_uuids": media_uuids,
    }

    if is_outbound:
        meta = json.dumps(meta_obj, ensure_ascii=False)
        await add_message(
            session,
            conv.id,
            MessageDirection.outbound,
            text_s,
            text_s or None,
            meta=meta,
        )
        conv.updated_at = datetime.now(timezone.utc)
        return "imported"

    user = await get_user_with_billing(session, owner_user_id)
    if not user:
        raise ValueError("user not found")

    translated, src_lang = await translate_to_russian(text_s) if text_s else ("", None)

    image_bytes: bytes | None = None
    image_mime: str | None = None
    if fetch_media and message_uuid and (has_media or media_uuids):
        row_fv = await session.scalar(
            select(FanvueConnection).where(FanvueConnection.user_id == owner_user_id)
        )
        if row_fv:
            try:
                fv_tok = await ensure_fanvue_access_token(session, row_fv)
                tok = access_token or fv_tok
                img = await fanvue_fetch_message_image_bytes(
                    tok,
                    fan_user_uuid=fan_uuid,
                    message_uuid=message_uuid,
                    media_uuids=media_uuids or [],
                )
                if img:
                    image_bytes, image_mime = img
                    meta_obj["has_image"] = True
            except Exception as e:
                log.warning("fanvue sync media fetch failed: %s", e)

    meta = json.dumps(meta_obj, ensure_ascii=False)
    await persist_inbound_chat_message(
        session,
        owner_user_id=owner_user_id,
        conv=conv,
        display=display,
        text_original=text_s,
        text_translated=translated if text_s else None,
        src_lang=src_lang,
        meta=meta,
        image_bytes=image_bytes,
        image_mime=image_mime,
        silent=silent,
    )
    return "imported"
