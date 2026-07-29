"""Instagram webhook → диалоги в БД."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.instagram.client import download_instagram_media
from app.db.models import InstagramConnection, Message, Platform
from app.db.repo import get_or_create_conversation, get_user_with_billing
from app.services.chat_message_meta import (
    parse_reactions,
    reactions_to_json,
    sync_actor_reactions,
)
from app.services.chat_ingest import (
    broadcast_inbound_after_commit,
    persist_inbound_chat_message,
)
from app.services.instagram_peer_profile import resolve_instagram_peer_display
from app.services.platform_connections import connection_studio_model_id
from app.services.translation import translate_to_russian

log = logging.getLogger(__name__)


def _instagram_account_match(account_id: str):
    return or_(
        InstagramConnection.instagram_user_id == account_id,
        InstagramConnection.instagram_alt_user_id == account_id,
    )


async def _resolve_instagram_connection(
    session: AsyncSession,
    entry: dict[str, Any],
) -> InstagramConnection | None:
    ig_account_id = str(entry.get("id") or "").strip()
    if ig_account_id and ig_account_id != "0":
        conn = await session.scalar(
            select(InstagramConnection).where(_instagram_account_match(ig_account_id))
        )
        if conn:
            return conn

    for event in entry.get("messaging") or []:
        if not isinstance(event, dict):
            continue
        recipient = event.get("recipient") or {}
        if not isinstance(recipient, dict):
            continue
        recipient_id = str(recipient.get("id") or "").strip()
        if not recipient_id or recipient_id == "0":
            continue
        conn = await session.scalar(
            select(InstagramConnection).where(_instagram_account_match(recipient_id))
        )
        if conn:
            log.info(
                "instagram webhook: matched account via recipient.id=%s",
                recipient_id[:16],
            )
            return conn

    if ig_account_id and ig_account_id != "0":
        log.info("instagram webhook: unknown account %s", ig_account_id[:16])
    return None


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


def _instagram_reaction_emoji(reaction: dict[str, Any]) -> str | None:
    raw = str(reaction.get("emoji") or "").strip()
    if raw:
        return raw
    name = str(reaction.get("reaction") or "").strip().lower()
    mapping = {
        "love": "❤️",
        "like": "👍",
        "laugh": "😂",
        "wow": "😮",
        "sad": "😢",
        "angry": "😡",
        "fire": "🔥",
    }
    return mapping.get(name)


async def _find_instagram_message(
    session: AsyncSession, owner_user_id: int, mid: str
) -> Message | None:
    if not mid:
        return None
    return await session.scalar(
        select(Message)
        .join(Message.conversation)
        .where(
            Message.conversation.has(user_id=owner_user_id),
            Message.platform_message_id == mid,
        )
        .limit(1)
    )


async def ingest_instagram_reaction_event(
    session: AsyncSession,
    conn: InstagramConnection,
    event: dict[str, Any],
) -> dict[str, Any]:
    reaction = event.get("reaction")
    if not isinstance(reaction, dict):
        return {"ok": True, "skipped": "bad_reaction"}

    sender = event.get("sender") or {}
    if not isinstance(sender, dict):
        return {"ok": True, "skipped": "bad_sender"}
    igsid = str(sender.get("id") or "").strip()
    ig_account_id = (conn.instagram_user_id or "").strip()
    ig_alt_account_id = (conn.instagram_alt_user_id or "").strip()
    if not igsid:
        return {"ok": True, "skipped": "missing_sender"}

    mid = str(reaction.get("mid") or "").strip()
    if not mid:
        return {"ok": True, "skipped": "missing_mid"}

    row = await _find_instagram_message(session, conn.user_id, mid)
    if not row:
        return {"ok": True, "skipped": "message_not_found"}

    action = str(reaction.get("action") or "react").strip().lower()
    actor = "owner" if igsid in {ig_account_id, ig_alt_account_id} else "peer"
    if action == "unreact":
        emojis: list[str] = []
    else:
        em = _instagram_reaction_emoji(reaction)
        emojis = [em] if em else []

    reactions = sync_actor_reactions(
        parse_reactions(row.reactions_json),
        actor=actor,
        emojis=emojis,
    )
    row.reactions_json = reactions_to_json(reactions)
    await session.commit()
    return {"ok": True, "message_id": row.id}


async def ingest_instagram_messaging_event(
    session: AsyncSession,
    conn: InstagramConnection,
    event: dict[str, Any],
) -> dict[str, Any]:
    if event.get("read") or event.get("postback"):
        return {"ok": True, "skipped": "non_message_event"}

    if event.get("reaction"):
        return await ingest_instagram_reaction_event(session, conn, event)

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
    ig_alt_account_id = (conn.instagram_alt_user_id or "").strip()
    if igsid in {ig_account_id, ig_alt_account_id}:
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
            payload = att.get("payload") or {}
            url = payload.get("url") if isinstance(payload, dict) else None
            if url and att_type in ("image", "animated_image", "story_mention", "share"):
                img = await download_instagram_media(str(url))
                if img:
                    image_bytes, image_mime = img
                    break
            if url and att_type in ("video", "ig_reel", "reel") and not image_bytes:
                vid = await download_instagram_media(str(url))
                if vid and vid[1].startswith("video/"):
                    image_bytes, image_mime = vid
                    break
                if not text_s:
                    text_s = str(url).strip()
            if att_type == "ephemeral":
                if not text_s:
                    text_s = "[исчезающее медиа недоступно через API]"
            if att_type in ("sticker", "like_heart") and url and not image_bytes:
                img = await download_instagram_media(str(url))
                if img:
                    image_bytes, image_mime = img
                    break

    if not text_s and not image_bytes:
        return {"ok": True, "skipped": "empty"}

    user = await get_user_with_billing(session, conn.user_id)
    if not user:
        raise ValueError("user not found")

    display = await resolve_instagram_peer_display(session, conn, igsid)

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
    log.info(
        "instagram webhook: saved user_id=%s conversation_id=%s peer=%s text=%r studio_model_id=%s",
        conn.user_id,
        conv_id,
        igsid,
        (text_s or "")[:120],
        conv.studio_model_id,
    )
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
    obj = str(body.get("object") or "").lower()
    entries = body.get("entry") or []
    if obj != "instagram":
        log.info("instagram webhook: skip object=%s", obj or "—")
        return {"ok": True, "skipped": "not_instagram"}

    log.info("instagram webhook: entries=%s", len(entries))
    processed = 0
    saved = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        messaging = entry.get("messaging") or []
        entry_id = str(entry.get("id") or "").strip()
        log.info(
            "instagram webhook: entry_id=%s messaging_events=%s",
            entry_id or "—",
            len(messaging) if isinstance(messaging, list) else 0,
        )
        if not entry_id or entry_id == "0":
            if not messaging:
                log.info("instagram webhook: skip test/empty entry")
                continue
        conn = await _resolve_instagram_connection(session, entry)
        if not conn:
            continue
        for event in messaging:
            if not isinstance(event, dict):
                continue
            try:
                result = await ingest_instagram_messaging_event(session, conn, event)
                processed += 1
                if result.get("conversation_id"):
                    saved += 1
                    log.info(
                        "instagram webhook: ingest ok conversation_id=%s",
                        result.get("conversation_id"),
                    )
                elif result.get("skipped"):
                    log.info("instagram webhook: event skipped: %s", result.get("skipped"))
            except Exception:
                log.exception(
                    "instagram ingest failed account=%s",
                    (conn.instagram_user_id or "")[:16],
                )
    log.info("instagram webhook: processed=%s saved=%s", processed, saved)
    return {"ok": True, "processed": processed, "saved": saved}
