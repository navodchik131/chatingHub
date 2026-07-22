from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Conversation,
    Message,
    MessageDirection,
    Platform,
    PushSubscription,
    User,
)


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
    *,
    telegram_connection_id: int | None = None,
    fanvue_connection_id: int | None = None,
    instagram_connection_id: int | None = None,
    studio_model_id: int | None = None,
) -> Conversation:
    # Unique key is (user_id, platform, external_chat_id, external_topic_id).
    # Do not filter by connection_id here — reconnects change connection ids and would
    # miss the row, then INSERT hits uq_conv_user_platform_chat_topic.
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
        if telegram_connection_id and conv.telegram_connection_id != telegram_connection_id:
            conv.telegram_connection_id = telegram_connection_id
        if fanvue_connection_id and conv.fanvue_connection_id != fanvue_connection_id:
            conv.fanvue_connection_id = fanvue_connection_id
        if instagram_connection_id and conv.instagram_connection_id != instagram_connection_id:
            conv.instagram_connection_id = instagram_connection_id
        if studio_model_id is not None and conv.studio_model_id != studio_model_id:
            conv.studio_model_id = studio_model_id
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
        telegram_connection_id=telegram_connection_id
        if platform == Platform.telegram
        else None,
        fanvue_connection_id=fanvue_connection_id
        if platform == Platform.fanvue
        else None,
        instagram_connection_id=instagram_connection_id
        if platform == Platform.instagram
        else None,
        studio_model_id=studio_model_id,
        created_at=now,
        updated_at=now,
    )
    session.add(conv)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(stmt)
        if existing is not None:
            if telegram_connection_id and existing.telegram_connection_id != telegram_connection_id:
                existing.telegram_connection_id = telegram_connection_id
            if fanvue_connection_id and existing.fanvue_connection_id != fanvue_connection_id:
                existing.fanvue_connection_id = fanvue_connection_id
            if instagram_connection_id and existing.instagram_connection_id != instagram_connection_id:
                existing.instagram_connection_id = instagram_connection_id
            if studio_model_id is not None and existing.studio_model_id != studio_model_id:
                existing.studio_model_id = studio_model_id
            if user_display_name and existing.user_display_name != user_display_name:
                existing.user_display_name = user_display_name
            existing.updated_at = datetime.now(timezone.utc)
            return existing
        raise
    return conv


async def add_message(
    session: AsyncSession,
    conversation_id: int,
    direction: MessageDirection,
    text_original: str,
    text_translated: str | None,
    meta: str | None = None,
    *,
    reply_to_message_id: int | None = None,
    platform_message_id: str | None = None,
    reactions_json: str | None = None,
    sender_user_id: int | None = None,
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        direction=direction,
        text_original=text_original,
        text_translated=text_translated,
        meta=meta,
        reply_to_message_id=reply_to_message_id,
        platform_message_id=platform_message_id,
        reactions_json=reactions_json,
        sender_user_id=sender_user_id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(msg)
    await session.flush()
    return msg


async def list_conversations(session: AsyncSession, user_id: int) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .where(
            Conversation.user_id == user_id,
            Conversation.is_hidden.is_(False),
        )
        .order_by(Conversation.updated_at.desc())
    )
    r = await session.execute(stmt)
    return list(r.scalars().all())


async def conversation_ids_with_outbound(
    session: AsyncSession, conv_ids: list[int]
) -> set[int]:
    if not conv_ids:
        return set()
    stmt = (
        select(Message.conversation_id)
        .where(
            Message.conversation_id.in_(conv_ids),
            Message.direction == MessageDirection.outbound,
        )
        .distinct()
    )
    r = await session.execute(stmt)
    return {int(x) for x in r.scalars().all()}


async def get_last_message(
    session: AsyncSession, conv_id: int, user_id: int
) -> Message | None:
    from sqlalchemy.orm import selectinload

    conv = await get_conversation(session, conv_id, user_id)
    if not conv:
        return None
    stmt = (
        select(Message)
        .where(Message.conversation_id == conv_id)
        .options(selectinload(Message.attachments))
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
    session: AsyncSession,
    conv_id: int,
    user_id: int,
    *,
    limit: int | None = None,
    before_id: int | None = None,
) -> list[Message]:
    """Сообщения по возрастанию id. При limit — последняя страница (или страница старше before_id)."""
    conv = await get_conversation(session, conv_id, user_id)
    if not conv:
        return []
    if limit is not None:
        stmt = select(Message).where(Message.conversation_id == conv_id)
        if before_id is not None:
            stmt = stmt.where(Message.id < int(before_id))
        stmt = stmt.order_by(Message.id.desc()).limit(int(limit))
        r = await session.execute(stmt)
        rows = list(r.scalars().all())
        rows.reverse()
        return rows
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
    prev_updated = conv.updated_at
    conv.last_read_message_id = int(max_id)
    await session.flush()
    # Чтение диалога не должно менять порядок в списке (onupdate на updated_at).
    conv.updated_at = prev_updated


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


async def list_push_subscriptions(
    session: AsyncSession, user_id: int
) -> list[PushSubscription]:
    r = await session.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    )
    return list(r.scalars().all())


async def upsert_push_subscription(
    session: AsyncSession,
    user_id: int,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str | None,
) -> None:
    stmt = select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row:
        row.user_id = user_id
        row.p256dh = p256dh
        row.auth = auth
        row.user_agent = user_agent
        return
    session.add(
        PushSubscription(
            user_id=user_id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            user_agent=user_agent,
        )
    )


async def delete_push_subscription(
    session: AsyncSession, user_id: int, endpoint: str
) -> bool:
    stmt = select(PushSubscription).where(
        PushSubscription.user_id == user_id,
        PushSubscription.endpoint == endpoint,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        return False
    await session.delete(row)
    return True


async def delete_push_subscription_by_id(
    session: AsyncSession, sub_id: int
) -> None:
    row = await session.get(PushSubscription, sub_id)
    if row:
        await session.delete(row)


async def list_mobile_push_tokens(
    session: AsyncSession, user_id: int
) -> list:
    from app.db.models import MobilePushToken

    r = await session.execute(
        select(MobilePushToken).where(MobilePushToken.user_id == user_id)
    )
    return list(r.scalars().all())


async def upsert_mobile_push_token(
    session: AsyncSession,
    user_id: int,
    expo_token: str,
    platform: str | None = None,
    device_name: str | None = None,
) -> None:
    from app.db.models import MobilePushToken

    stmt = select(MobilePushToken).where(MobilePushToken.expo_token == expo_token)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row:
        row.user_id = user_id
        row.platform = platform
        row.device_name = device_name
        return
    session.add(
        MobilePushToken(
            user_id=user_id,
            expo_token=expo_token,
            platform=platform,
            device_name=device_name,
        )
    )


async def delete_mobile_push_token(
    session: AsyncSession, user_id: int, expo_token: str
) -> bool:
    from app.db.models import MobilePushToken

    stmt = select(MobilePushToken).where(
        MobilePushToken.user_id == user_id,
        MobilePushToken.expo_token == expo_token,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        return False
    await session.delete(row)
    return True


async def delete_mobile_push_token_by_id(session: AsyncSession, token_id: int) -> None:
    from app.db.models import MobilePushToken

    row = await session.get(MobilePushToken, token_id)
    if row:
        await session.delete(row)
