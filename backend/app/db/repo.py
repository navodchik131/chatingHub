from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Conversation, Message, MessageDirection, Platform, User


async def get_user_with_billing(session: AsyncSession, user_id: int) -> User | None:
    stmt = (
        select(User)
        .where(User.id == user_id, User.is_active.is_(True))
        .options(
            selectinload(User.subscription),
            selectinload(User.credit_account),
        )
    )
    r = await session.execute(stmt)
    return r.scalar_one_or_none()


async def get_or_create_conversation(
    session: AsyncSession,
    user_id: int,
    platform: Platform,
    external_chat_id: str,
    external_topic_id: str,
    user_display_name: str | None,
    telegram_photo_file_id: str | None = None,
) -> Conversation:
    stmt = select(Conversation).where(
        Conversation.user_id == user_id,
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
        if (
            platform == Platform.telegram
            and telegram_photo_file_id
            and conv.telegram_photo_file_id != telegram_photo_file_id
        ):
            conv.telegram_photo_file_id = telegram_photo_file_id
        conv.updated_at = now
        return conv
    conv = Conversation(
        user_id=user_id,
        platform=platform,
        external_chat_id=external_chat_id,
        external_topic_id=external_topic_id,
        user_display_name=user_display_name,
        telegram_photo_file_id=telegram_photo_file_id
        if platform == Platform.telegram
        else None,
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


async def list_conversations(session: AsyncSession, user_id: int) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    )
    r = await session.execute(stmt)
    return list(r.scalars().all())


async def get_last_message(
    session: AsyncSession, conv_id: int, user_id: int
) -> Message | None:
    conv = await get_conversation(session, conv_id, user_id)
    if not conv:
        return None
    stmt = (
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.id.desc())
        .limit(1)
    )
    r = await session.execute(stmt)
    return r.scalar_one_or_none()


async def get_conversation(
    session: AsyncSession, conv_id: int, user_id: int
) -> Conversation | None:
    stmt = select(Conversation).where(
        Conversation.id == conv_id, Conversation.user_id == user_id
    )
    r = await session.execute(stmt)
    return r.scalar_one_or_none()


async def count_rows(session: AsyncSession) -> tuple[int, int]:
    nc = await session.scalar(select(func.count()).select_from(Conversation))
    nm = await session.scalar(select(func.count()).select_from(Message))
    return int(nc or 0), int(nm or 0)


async def count_rows_for_user(session: AsyncSession, user_id: int) -> tuple[int, int]:
    nc = await session.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.user_id == user_id)
    )
    nm = await session.scalar(
        select(func.count())
        .select_from(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == user_id)
    )
    return int(nc or 0), int(nm or 0)


async def list_messages(
    session: AsyncSession, conv_id: int, user_id: int
) -> list[Message]:
    conv = await get_conversation(session, conv_id, user_id)
    if not conv:
        return []
    stmt = (
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.id.asc())
    )
    r = await session.execute(stmt)
    return list(r.scalars().all())


async def mark_conversation_read(
    session: AsyncSession, conv_id: int, user_id: int
) -> None:
    conv = await get_conversation(session, conv_id, user_id)
    if not conv:
        return
    max_id = await session.scalar(
        select(func.max(Message.id)).where(Message.conversation_id == conv_id)
    )
    if max_id is None:
        return
    conv.last_read_message_id = int(max_id)
    conv.updated_at = datetime.now(timezone.utc)


async def unread_inbound_count(
    session: AsyncSession, conv_id: int, user_id: int
) -> int:
    conv = await get_conversation(session, conv_id, user_id)
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
