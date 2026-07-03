"""Сериализация сообщений чата с вложениями."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import BotResponseEvent, Message, MessageAttachment
from app.schemas import MessageAttachmentOut, MessageOut, MessageReactionOut
from app.services.chat_attachment import create_chat_attachment_access_token
from app.services.chat_message_meta import parse_reactions


def attachment_public_url(*, owner_id: int, att: MessageAttachment) -> str:
    tok = create_chat_attachment_access_token(user_id=owner_id, attachment_id=att.id)
    return f"/api/chat/attachment?t={tok}"


def parse_companion_message_meta(meta: str | None) -> tuple[bool, int | None]:
    if not meta:
        return False, None
    try:
        data = json.loads(meta)
    except json.JSONDecodeError:
        return False, None
    if not isinstance(data, dict):
        return False, None
    if not data.get("companion_bot"):
        return False, None
    raw_id = data.get("bot_response_event_id")
    try:
        event_id = int(raw_id) if raw_id is not None else None
    except (TypeError, ValueError):
        event_id = None
    return True, event_id


def message_to_out(
    msg: Message,
    *,
    owner_id: int,
    reply_preview: str | None = None,
    operator_rating: int | None = None,
    bot_response_event_id: int | None = None,
    platform_sync_ok: bool | None = None,
) -> MessageOut:
    atts = [
        MessageAttachmentOut(
            id=a.id,
            kind=a.kind.value if hasattr(a.kind, "value") else str(a.kind),
            url=attachment_public_url(owner_id=owner_id, att=a),
            mime_type=a.mime_type,
        )
        for a in (msg.attachments or [])
    ]
    reactions = [
        MessageReactionOut(emoji=r["emoji"], actor=r["actor"])  # type: ignore[arg-type]
        for r in parse_reactions(getattr(msg, "reactions_json", None))
    ]
    companion_bot, meta_event_id = parse_companion_message_meta(getattr(msg, "meta", None))
    event_id = bot_response_event_id if bot_response_event_id is not None else meta_event_id
    return MessageOut(
        id=msg.id,
        direction=msg.direction,
        text_original=msg.text_original,
        text_translated=msg.text_translated,
        created_at=msg.created_at,
        attachments=atts,
        reply_to_message_id=getattr(msg, "reply_to_message_id", None),
        reply_preview=reply_preview,
        reactions=reactions,
        companion_bot=companion_bot,
        bot_response_event_id=event_id,
        operator_rating=operator_rating,
        platform_sync_ok=platform_sync_ok,
    )


async def _companion_ratings_for_messages(
    session: AsyncSession, message_ids: list[int]
) -> dict[int, tuple[int | None, int | None]]:
    if not message_ids:
        return {}
    rows = (
        await session.execute(
            select(
                BotResponseEvent.outbound_message_id,
                BotResponseEvent.id,
                BotResponseEvent.operator_rating,
            ).where(BotResponseEvent.outbound_message_id.in_(message_ids))
        )
    ).all()
    out: dict[int, tuple[int | None, int | None]] = {}
    for outbound_id, event_id, rating in rows:
        if outbound_id is not None:
            out[int(outbound_id)] = (int(event_id), rating)
    return out


async def load_messages_for_api(
    session: AsyncSession,
    rows: list[Message],
    *,
    owner_id: int,
) -> list[MessageOut]:
    if not rows:
        return []
    ids = [m.id for m in rows]
    stmt = (
        select(Message)
        .where(Message.id.in_(ids))
        .options(selectinload(Message.attachments))
    )
    r = await session.execute(stmt)
    by_id = {m.id: m for m in r.scalars().all()}
    ordered = [by_id[i] for i in ids if i in by_id]

    reply_ids = [m.reply_to_message_id for m in ordered if m.reply_to_message_id]
    reply_previews: dict[int, str] = {}
    if reply_ids:
        rr = await session.execute(select(Message).where(Message.id.in_(reply_ids)))
        for rm in rr.scalars().all():
            text = (rm.text_original or rm.text_translated or "").strip()
            reply_previews[rm.id] = text[:160] if text else "📷 Изображение"

    ratings = await _companion_ratings_for_messages(session, ids)

    result: list[MessageOut] = []
    for m in ordered:
        event_id, rating = ratings.get(m.id, (None, None))
        result.append(
            message_to_out(
                m,
                owner_id=owner_id,
                reply_preview=reply_previews.get(m.reply_to_message_id)
                if m.reply_to_message_id
                else None,
                operator_rating=rating,
                bot_response_event_id=event_id,
            )
        )
    return result


def message_preview_text(msg: Message) -> str | None:
    text = (msg.text_translated or msg.text_original or "").strip()
    if text:
        return text[:280]
    if msg.attachments:
        return "📷 Изображение"
    return None


async def add_message_attachment(
    session: AsyncSession,
    *,
    message_id: int,
    relative_path: str,
    mime_type: str,
) -> MessageAttachment:
    from app.db.models import MessageAttachmentKind

    att = MessageAttachment(
        message_id=message_id,
        kind=MessageAttachmentKind.image,
        relative_path=relative_path,
        mime_type=mime_type,
    )
    session.add(att)
    await session.flush()
    return att
