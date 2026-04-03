from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message, MessageDirection, Platform


async def get_or_create_conversation(
    session: AsyncSession,
    platform: Platform,
    external_chat_id: str,
    external_topic_id: str,
    user_display_name: str | None,
) -> Conversation:
    stmt = select(Conversation).where(
        Conversation.platform == platform,
        Conversation.external_chat_id == external_chat_id,
        Conversation.external_topic_id == external_topic_id,
    )
    r = await session.execute(stmt)
    conv = r.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if conv:
        if user_display_name and conv.user_display_name != user_display_name:
            conv.user_display_name = user_display_name
        conv.updated_at = now
        return conv
    conv = Conversation(
        platform=platform,
        external_chat_id=external_chat_id,
        external_topic_id=external_topic_id,
        user_display_name=user_display_name,
        created_at=now,
        updated_at=now,
    )
    session.add(conv)
    await session.flush()
    return conv


async def add_message(
    session: AsyncSession,
    conversation_id: int,
    direction: MessageDirection,
    text_original: str,
    text_translated: str | None,
    meta: str | None = None,
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        direction=direction,
        text_original=text_original,
        text_translated=text_translated,
        meta=meta,
        created_at=datetime.now(timezone.utc),
    )
    session.add(msg)
    await session.flush()
    return msg


async def list_conversations(session: AsyncSession) -> list[Conversation]:
    stmt = select(Conversation).order_by(Conversation.updated_at.desc())
    r = await session.execute(stmt)
    return list(r.scalars().all())


async def get_last_message(session: AsyncSession, conv_id: int) -> Message | None:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.id.desc())
        .limit(1)
    )
    r = await session.execute(stmt)
    return r.scalar_one_or_none()


async def get_conversation(session: AsyncSession, conv_id: int) -> Conversation | None:
    stmt = select(Conversation).where(Conversation.id == conv_id)
    r = await session.execute(stmt)
    return r.scalar_one_or_none()


async def count_rows(session: AsyncSession) -> tuple[int, int]:
    """(число диалогов, число сообщений)."""
    nc = await session.scalar(select(func.count()).select_from(Conversation))
    nm = await session.scalar(select(func.count()).select_from(Message))
    return int(nc or 0), int(nm or 0)


async def list_messages(
    session: AsyncSession, conv_id: int
) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.id.asc())
    )
    r = await session.execute(stmt)
    return list(r.scalars().all())


async def mark_conversation_read(session: AsyncSession, conv_id: int) -> None:
    """Помечает диалог прочитанным до последнего сообщения."""
    conv = await get_conversation(session, conv_id)
    if not conv:
        return
    max_id = await session.scalar(
        select(func.max(Message.id)).where(Message.conversation_id == conv_id)
    )
    if max_id is None:
        return
    conv.last_read_message_id = int(max_id)
    conv.updated_at = datetime.now(timezone.utc)


async def unread_inbound_count(session: AsyncSession, conv_id: int) -> int:
    """Число входящих сообщений после last_read_message_id."""
    conv = await get_conversation(session, conv_id)
    if not conv:
        return 0
    last = conv.last_read_message_id or 0
    stmt = (
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conv_id,
            Message.direction == MessageDirection.inbound,
            Message.id > last,
        )
    )
    return int(await session.scalar(stmt) or 0)
