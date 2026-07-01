"""Instagram webhook → диалоги в БД."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.instagram.client import download_instagram_media
from app.db.models import InstagramConnection, Message, Platform
from app.db.repo import get_or_create_conversation, get_user_with_billing
from app.services.chat_ingest import (
    broadcast_inbound_after_commit,
    persist_inbound_chat_message,
)
from app.services.platform_connections import connection_studio_model_id
from app.services.translation import translate_to_russian

log = logging.getLogger(__name__)


async def instagram_message_exists(
    session: AsyncSession, owner_user_id: int, message_id: str
) -> bool:
    if not message_id:
        return False
    row = await session.scalar(
        select(Message.id)
        .join(Message.conversation)
        .where(
            Message.conversation.has(user_id=owner_user_id),
            Message.platform_message_id == message_id,
        )
        .limit(1)
    )
    return row is not None


async def ingest_instagram_messaging_event(
    session: AsyncSession,
    conn: InstagramConnection,
    event: dict[str, Any],
) -> dict[str, Any]:
    if event.get("read") or event.get("reaction") or event.get("postback"):
        return {"ok": True, "skipped": "non_message_event"}

    msg = event.get("message")
    if not isinstance(msg, dict):
        return {"ok": True, "skipped": "no_message"}

    if msg.get("is_echo"):
        return {"ok": True, "skipped": "echo"}

    if msg.get("is_deleted"):
        return {"ok": True, "skipped": "deleted"}

    if msg.get("is_unsupported"):
        return {"ok": True, "skipped": "unsupported"}

    sender = event.get("sender") or {}
    if not isinstance(sender, dict):
        return {"ok": True, "skipped": "bad_sender"}

    igsid = str(sender.get("id") or "").strip()
    if not igsid:
        return {"ok": True, "skipped": "missing_sender"}

    ig_account_id = (conn.instagram_user_id or "").strip()
    if igsid == ig_account_id:
        return {"ok": True, "skipped": "self_message"}

    mid = str(msg.get("mid") or "").strip()
    if mid and await instagram_message_exists(session, conn.user_id, mid):
        return {"ok": True, "skipped": "duplicate"}

    text_s = str(msg.get("text") or "").strip()
    image_bytes: bytes | None = None
    image_mime: str | None = None
    attachments = msg.get("attachments")
    if isinstance(attachments, list):
        for att in attachments:
            if not isinstance(att, dict):
                continue
            att_type = str(att.get("type") or "").lower()
            if att_type in ("image", "story_mention", "share", "ig_reel", "reel", "video"):
                payload = att.get("payload") or {}
                url = payload.get("url") if isinstance(payload, dict) else None
                if url and att_type == "image":
                    img = await download_instagram_media(str(url))
                    if img:
                        image_bytes, image_mime = img
                        break
                elif url and not text_s:
                    text_s = str(url).strip()
            if att_type == "ephemeral":
                if not text_s:
                    text_s = "[исчезающее медиа недоступно через API]"

    if not text_s and not image_bytes:
        return {"ok": True, "skipped": "empty"}

    user = await get_user_with_billing(session, conn.user_id)
    if not user:
        raise ValueError("user not found")

    display = f"Instagram {igsid[:10]}"

    conv = await get_or_create_conversation(
        session,
        conn.user_id,
        Platform.instagram,
        igsid,
        ig_account_id,
        display,
        instagram_connection_id=conn.id,
        studio_model_id=connection_studio_model_id(conn),
    )

    if text_s and not conv.auto_translate_disabled:
        translated, src_lang = await translate_to_russian(text_s)
    else:
        translated, src_lang = "", None

    meta = json.dumps({"instagram_mid": mid}, ensure_ascii=False) if mid else None

    conv_id, payload = await persist_inbound_chat_message(
        session,
        owner_user_id=conn.user_id,
        conv=conv,
        display=display,
        text_original=text_s or "",
        text_translated=translated or None,
        src_lang=src_lang,
        meta=meta,
        image_bytes=image_bytes,
        image_mime=image_mime,
        silent=True,
        platform_message_id=mid or None,
    )
    if payload is None:
        return {"ok": True, "skipped": "blocked"}
    await session.commit()
    await broadcast_inbound_after_commit(
        owner_user_id=conn.user_id,
        conv_id=conv_id,
        payload=payload,
        display=display,
        conv=conv,
        text_original=text_s or "",
        text_translated=translated or None,
        image_bytes=image_bytes,
    )
    return {"ok": True, "conversation_id": conv_id}


async def ingest_instagram_webhook_body(
    session: AsyncSession,
    body: dict[str, Any],
) -> dict[str, Any]:
    if str(body.get("object") or "").lower() != "instagram":
        return {"ok": True, "skipped": "not_instagram"}

    processed = 0
    for entry in body.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        ig_account_id = str(entry.get("id") or "").strip()
        if not ig_account_id:
            continue
        conn = await session.scalar(
            select(InstagramConnection).where(
                InstagramConnection.instagram_user_id == ig_account_id
            )
        )
        if not conn:
            log.info("instagram webhook: unknown account %s", ig_account_id[:8])
            continue
        for event in entry.get("messaging") or []:
            if not isinstance(event, dict):
                continue
            try:
                await ingest_instagram_messaging_event(session, conn, event)
                processed += 1
            except Exception:
                log.exception(
                    "instagram ingest failed account=%s", ig_account_id[:8]
                )
    return {"ok": True, "processed": processed}
