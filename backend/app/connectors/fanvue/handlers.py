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
from app.services.chat_ingest import (
    broadcast_inbound_after_commit,
    persist_inbound_chat_message,
)
from app.services.chat_messages import message_to_out
from app.services.companion_bot.schedule import schedule_companion_reply
from app.services.translation import translate_to_russian

log = logging.getLogger(__name__)


def _meta_needle_fanvue_message_uuid(message_uuid: str) -> str:
    return f'"fanvue_message_uuid": "{message_uuid}"'


async def fanvue_message_exists(
    session: AsyncSession, owner_user_id: int, message_uuid: str
) -> bool:
    if not message_uuid:
        return False
    by_platform = await session.scalar(
        select(Message.id)
        .join(Message.conversation)
        .where(
            Message.conversation.has(user_id=owner_user_id),
            Message.platform_message_id == message_uuid,
        )
        .limit(1)
    )
    if by_platform:
        return True
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
    conn: FanvueConnection,
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

    owner_user_id = conn.user_id
    creator_uuid = (conn.creator_uuid or "").strip() or str(recipient_uuid or "").strip() or "default"
    if fan_uuid == creator_uuid:
        log.debug("fanvue webhook: skip creator self-message uuid=%s", message_uuid)
        return {"ok": True, "skipped": "self_message"}

    if message_uuid and await fanvue_message_exists(session, owner_user_id, message_uuid):
        log.debug("fanvue duplicate webhook message %s", message_uuid)
        return {"ok": True, "skipped": "duplicate"}

    user = await get_user_with_billing(session, owner_user_id)
    if not user:
        raise ValueError("user not found")

    display = sender.get("displayName") or sender.get("handle") or fan_uuid
    if not isinstance(display, str):
        display = str(display)

    image_bytes: bytes | None = None
    image_mime: str | None = None
    if message_uuid and (has_media or media_uuids):
        try:
            from app.services.fanvue_connection import ensure_fanvue_access_token

            fv_tok = await ensure_fanvue_access_token(session, conn)
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

    from app.services.platform_connections import connection_studio_model_id

    conv = await get_or_create_conversation(
        session,
        owner_user_id,
        Platform.fanvue,
        fan_uuid,
        creator_uuid,
        display,
        fanvue_connection_id=conn.id,
        studio_model_id=connection_studio_model_id(conn),
    )

    if text_s and not conv.auto_translate_disabled:
        translated, src_lang = await translate_to_russian(text_s)
    else:
        translated, src_lang = "", None

    reply_to_message_id: int | None = None
    reply_uuid = str(
        msg.get("replyToMessageUuid") or msg.get("reply_to_message_uuid") or ""
    ).strip()
    if reply_uuid:
        parent = await session.scalar(
            select(Message).where(
                Message.conversation_id == conv.id,
                Message.platform_message_id == reply_uuid,
            )
        )
        if parent:
            reply_to_message_id = parent.id

    reactions_json: str | None = None
    raw_reactions = msg.get("reactions")
    if isinstance(raw_reactions, list) and raw_reactions:
        parsed: list[dict[str, str]] = []
        for item in raw_reactions:
            if isinstance(item, dict):
                em = str(item.get("emoji") or "").strip()
                if em:
                    parsed.append({"emoji": em, "actor": "peer"})
            elif isinstance(item, str) and item.strip():
                parsed.append({"emoji": item.strip(), "actor": "peer"})
        if parsed:
            from app.services.chat_message_meta import reactions_to_json

            reactions_json = reactions_to_json(parsed)

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

    conv_id, payload = await persist_inbound_chat_message(
        session,
        owner_user_id=owner_user_id,
        conv=conv,
        display=display,
        text_original=text_s,
        text_translated=translated if text_s and not conv.auto_translate_disabled else None,
        src_lang=src_lang,
        meta=meta,
        image_bytes=image_bytes,
        image_mime=image_mime,
        reply_to_message_id=reply_to_message_id,
        platform_message_id=message_uuid or None,
        silent=True,
    )
    if payload is None:
        return {"ok": True, "skipped": "blocked"}
    if reactions_json:
        last = await session.scalar(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.id.desc())
            .limit(1)
        )
        if last:
            last.reactions_json = reactions_json
            payload = message_to_out(last, owner_id=owner_user_id).model_dump(mode="json")
    await session.commit()
    await broadcast_inbound_after_commit(
        owner_user_id=owner_user_id,
        conv_id=conv_id,
        payload=payload,
        display=display,
        conv=conv,
        text_original=text_s,
        text_translated=translated if text_s and not conv.auto_translate_disabled else None,
        image_bytes=image_bytes,
    )
    trigger_message_id = int(payload["id"])
    schedule_companion_reply(
        owner_user_id=owner_user_id,
        conv_id=conv_id,
        trigger_message_id=trigger_message_id,
    )
    log.info(
        "fanvue webhook ingested conv=%s msg_uuid=%s fan=%s",
        conv_id,
        message_uuid or "?",
        fan_uuid[:8],
    )

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
    conn: FanvueConnection | None = None,
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

    from app.services.platform_connections import connection_studio_model_id

    conv = await get_or_create_conversation(
        session,
        owner_user_id,
        Platform.fanvue,
        fan_uuid,
        creator_uuid,
        display,
        fanvue_connection_id=conn.id if conn else None,
        studio_model_id=connection_studio_model_id(conn) if conn else None,
    )

    meta_obj: dict[str, Any] = {
        "fanvue_message_uuid": message_uuid or None,
        "sender_uuid": sender_uuid,
        "recipient_uuid": creator_uuid if is_outbound else fan_uuid,
        "ingest": "fanvue.history.sync",
        "media_uuids": media_uuids,
    }

    reply_to_message_id: int | None = None
    reply_uuid = str(
        msg.get("replyToMessageUuid") or msg.get("reply_to_message_uuid") or ""
    ).strip()
    if reply_uuid:
        parent = await session.scalar(
            select(Message).where(
                Message.conversation_id == conv.id,
                Message.platform_message_id == reply_uuid,
            )
        )
        if parent:
            reply_to_message_id = parent.id

    if is_outbound:
        meta = json.dumps(meta_obj, ensure_ascii=False)
        await add_message(
            session,
            conv.id,
            MessageDirection.outbound,
            text_s,
            text_s or None,
            meta=meta,
            reply_to_message_id=reply_to_message_id,
            platform_message_id=message_uuid or None,
        )
        conv.updated_at = datetime.now(timezone.utc)
        return "imported"

    user = await get_user_with_billing(session, owner_user_id)
    if not user:
        raise ValueError("user not found")

    if text_s and not conv.auto_translate_disabled:
        translated, src_lang = await translate_to_russian(text_s)
    else:
        translated, src_lang = "", None

    image_bytes: bytes | None = None
    image_mime: str | None = None
    if fetch_media and message_uuid and (has_media or media_uuids):
        row_fv = conn
        if not row_fv:
            row_fv = await session.scalar(
                select(FanvueConnection).where(
                    FanvueConnection.user_id == owner_user_id,
                    FanvueConnection.creator_uuid == creator_uuid.strip(),
                )
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
    conv_id, payload = await persist_inbound_chat_message(
        session,
        owner_user_id=owner_user_id,
        conv=conv,
        display=display,
        text_original=text_s,
        text_translated=translated if text_s and not conv.auto_translate_disabled else None,
        src_lang=src_lang,
        meta=meta,
        image_bytes=image_bytes,
        image_mime=image_mime,
        silent=True,
        reply_to_message_id=reply_to_message_id,
        platform_message_id=message_uuid or None,
    )
    if payload is None:
        return "blocked"
    if not silent:
        await session.commit()
        await broadcast_inbound_after_commit(
            owner_user_id=owner_user_id,
            conv_id=conv_id,
            payload=payload,
            display=display,
            conv=conv,
            text_original=text_s,
            text_translated=translated if text_s and not conv.auto_translate_disabled else None,
            image_bytes=image_bytes,
        )
    return "imported"
