"""Сериализация сообщений чата с вложениями."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Message, MessageAttachment
from app.schemas import MessageAttachmentOut, MessageOut
from app.services.chat_attachment import create_chat_attachment_access_token


def attachment_public_url(*, owner_id: int, att: MessageAttachment) -> str:
    tok = create_chat_attachment_access_token(user_id=owner_id, attachment_id=att.id)
    return f"/api/chat/attachment?t={tok}"


def message_to_out(msg: Message, *, owner_id: int) -> MessageOut:
    atts = [
        MessageAttachmentOut(
            id=a.id,
            kind=a.kind.value if hasattr(a.kind, "value") else str(a.kind),
            url=attachment_public_url(owner_id=owner_id, att=a),
            mime_type=a.mime_type,
        )
        for a in (msg.attachments or [])
    ]
    return MessageOut(
        id=msg.id,
        direction=msg.direction,
        text_original=msg.text_original,
        text_translated=msg.text_translated,
        created_at=msg.created_at,
        attachments=atts,
    )


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
    return [message_to_out(m, owner_id=owner_id) for m in ordered]


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
