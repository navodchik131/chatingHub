"""Доступ к БД Stars Business (OWNER / OPERATOR)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import (
    StarsBusinessConnection,
    StarsBusinessFanChat,
    StarsBusinessOperator,
    StarsBusinessOrder,
    User,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_connection(session: AsyncSession, owner_tg_user_id: int) -> StarsBusinessConnection | None:
    return await session.get(StarsBusinessConnection, owner_tg_user_id)


async def get_connection_for_workspace_user(
    session: AsyncSession,
    workspace_owner_user_id: int,
) -> StarsBusinessConnection | None:
    """Business OWNER, привязанный к владельцу workspace (Unibox)."""
    return await session.scalar(
        select(StarsBusinessConnection)
        .where(
            StarsBusinessConnection.user_id == int(workspace_owner_user_id),
            StarsBusinessConnection.is_enabled.is_(True),
        )
        .order_by(StarsBusinessConnection.updated_at.desc())
        .limit(1)
    )


async def get_connection_by_connection_id(
    session: AsyncSession,
    connection_id: str,
) -> StarsBusinessConnection | None:
    cid = (connection_id or "").strip()
    if not cid:
        return None
    return await session.scalar(
        select(StarsBusinessConnection).where(StarsBusinessConnection.connection_id == cid)
    )


async def get_active_connection(session: AsyncSession) -> StarsBusinessConnection | None:
    """Этап 1: один OWNER — первая активная запись."""
    return await session.scalar(
        select(StarsBusinessConnection)
        .where(StarsBusinessConnection.is_enabled.is_(True))
        .order_by(StarsBusinessConnection.updated_at.desc())
        .limit(1)
    )


async def upsert_business_connection(
    session: AsyncSession,
    *,
    owner_tg_user_id: int,
    connection_id: str,
    is_enabled: bool,
    owner_user_chat_id: int | None,
) -> StarsBusinessConnection:
    row = await session.get(StarsBusinessConnection, owner_tg_user_id)
    if row is None:
        row = StarsBusinessConnection(
            owner_tg_user_id=owner_tg_user_id,
            connection_id=connection_id,
            is_enabled=is_enabled,
            owner_user_chat_id=owner_user_chat_id,
            updated_at=utcnow(),
        )
        session.add(row)
    else:
        row.connection_id = connection_id
        row.is_enabled = is_enabled
        row.owner_user_chat_id = owner_user_chat_id
        row.updated_at = utcnow()
    if row.user_id is None:
        owner_user = await session.scalar(
            select(User).where(
                User.telegram_id == owner_tg_user_id,
                User.is_active.is_(True),
                User.parent_user_id.is_(None),
            )
        )
        if owner_user is not None:
            row.user_id = int(owner_user.id)
    await session.flush()
    await sync_operators_from_env(session, owner_tg_user_id)
    return row


async def sync_operators_from_env(session: AsyncSession, owner_tg_user_id: int) -> None:
    """OPERATOR whitelist из env — при первом подключении OWNER."""
    for op_id in settings.stars_business_operator_ids:
        existing = await session.scalar(
            select(StarsBusinessOperator).where(
                StarsBusinessOperator.owner_tg_user_id == owner_tg_user_id,
                StarsBusinessOperator.operator_tg_user_id == op_id,
            )
        )
        if existing:
            existing.is_active = True
            continue
        session.add(
            StarsBusinessOperator(
                owner_tg_user_id=owner_tg_user_id,
                operator_tg_user_id=op_id,
                is_active=True,
            )
        )
    await session.flush()


async def is_operator(
    session: AsyncSession,
    *,
    owner_tg_user_id: int,
    telegram_user_id: int,
) -> bool:
    row = await session.scalar(
        select(StarsBusinessOperator).where(
            StarsBusinessOperator.owner_tg_user_id == owner_tg_user_id,
            StarsBusinessOperator.operator_tg_user_id == telegram_user_id,
            StarsBusinessOperator.is_active.is_(True),
        )
    )
    if row is not None:
        return True
    # Этап 1: один OWNER — env whitelist, если sync в БД ещё не был (деплой до business_connection).
    if telegram_user_id in settings.stars_business_operator_ids:
        return True
    return False


async def sync_operators_for_active_owner_from_env(session: AsyncSession) -> None:
    """Подтянуть OPERATOR из env после деплоя без переподключения Business."""
    conn = await get_active_connection(session)
    if not conn or not conn.is_enabled:
        return
    await sync_operators_from_env(session, int(conn.owner_tg_user_id))


async def is_owner(session: AsyncSession, owner_tg_user_id: int, telegram_user_id: int) -> bool:
    return owner_tg_user_id == telegram_user_id


async def upsert_fan_inbound(
    session: AsyncSession,
    *,
    owner_tg_user_id: int,
    fan_chat_id: int,
    fan_display_name: str | None,
    inbound_at: datetime,
) -> None:
    row = await session.scalar(
        select(StarsBusinessFanChat).where(
            StarsBusinessFanChat.owner_tg_user_id == owner_tg_user_id,
            StarsBusinessFanChat.fan_chat_id == fan_chat_id,
        )
    )
    if row is None:
        session.add(
            StarsBusinessFanChat(
                owner_tg_user_id=owner_tg_user_id,
                fan_chat_id=fan_chat_id,
                fan_display_name=fan_display_name,
                last_inbound_at=inbound_at,
                updated_at=utcnow(),
            )
        )
    else:
        row.fan_display_name = fan_display_name or row.fan_display_name
        row.last_inbound_at = inbound_at
        row.updated_at = utcnow()
    await session.flush()


async def list_fan_chats(
    session: AsyncSession,
    owner_tg_user_id: int,
    *,
    limit: int = 30,
) -> list[StarsBusinessFanChat]:
    rows = (
        await session.scalars(
            select(StarsBusinessFanChat)
            .where(StarsBusinessFanChat.owner_tg_user_id == owner_tg_user_id)
            .order_by(StarsBusinessFanChat.last_inbound_at.desc())
            .limit(limit)
        )
    ).all()
    return list(rows)


async def resolve_connection_for_workspace(
    session: AsyncSession,
    workspace_owner_user_id: int,
) -> StarsBusinessConnection | None:
    """
    Business OWNER для Unibox: явная user_id или автопривязка по users.telegram_id.
    Бот /paid работает по owner_tg_user_id; кабинет — по users.id workspace owner.
    """
    conn = await get_connection_for_workspace_user(session, workspace_owner_user_id)
    if conn:
        return conn
    owner_user = await session.get(User, workspace_owner_user_id)
    tg_id = int(owner_user.telegram_id) if owner_user and owner_user.telegram_id else None
    if tg_id:
        linked = await link_connection_to_workspace_user(
            session,
            workspace_owner_user_id=workspace_owner_user_id,
            owner_tg_user_id=tg_id,
        )
        if linked and linked.is_enabled:
            return linked

    # Вход в кабинет по email: telegram_id пустой, но Business OWNER уже в БД (бот /paid работал).
    active = await get_active_connection(session)
    if not active or not active.is_enabled:
        return None
    wid = int(workspace_owner_user_id)
    if active.user_id is not None and int(active.user_id) != wid:
        return None
    linked = await link_connection_to_workspace_user(
        session,
        workspace_owner_user_id=wid,
        owner_tg_user_id=int(active.owner_tg_user_id),
    )
    if linked and linked.is_enabled:
        return linked
    return None


async def link_connection_to_workspace_user(
    session: AsyncSession,
    *,
    workspace_owner_user_id: int,
    owner_tg_user_id: int,
) -> StarsBusinessConnection | None:
    """Явная привязка Business OWNER к user_id workspace (интеграции)."""
    row = await get_connection(session, owner_tg_user_id)
    if not row:
        return None
    row.user_id = int(workspace_owner_user_id)
    row.updated_at = utcnow()
    await session.flush()
    return row


async def create_order(
    session: AsyncSession,
    *,
    owner_tg_user_id: int,
    operator_tg_user_id: int,
    fan_chat_id: int,
    star_count: int,
    caption: str | None,
    media_relative_path: str,
    media_type: str,
    conversation_id: int | None = None,
    pack_id: int | None = None,
    asset_id: int | None = None,
    created_by_user_id: int | None = None,
) -> StarsBusinessOrder:
    order = StarsBusinessOrder(
        owner_tg_user_id=owner_tg_user_id,
        operator_tg_user_id=operator_tg_user_id,
        fan_chat_id=fan_chat_id,
        star_count=star_count,
        caption=caption,
        media_relative_path=media_relative_path,
        media_type=media_type,
        status="draft",
        conversation_id=conversation_id,
        pack_id=pack_id,
        asset_id=asset_id,
        created_by_user_id=created_by_user_id,
    )
    session.add(order)
    await session.flush()
    return order


async def mark_order_sent(
    session: AsyncSession,
    order: StarsBusinessOrder,
    *,
    platform_message_id: int,
    unibox_message_id: int | None = None,
) -> None:
    order.status = "sent"
    order.platform_message_id = platform_message_id
    order.sent_at = utcnow()
    order.error_code = None
    if unibox_message_id is not None:
        order.unibox_message_id = unibox_message_id
    await session.flush()


async def mark_order_failed(session: AsyncSession, order: StarsBusinessOrder, *, error_code: str) -> None:
    order.status = "failed"
    order.error_code = error_code[:64]
    await session.flush()


async def mark_order_paid(session: AsyncSession, order_id: int) -> StarsBusinessOrder | None:
    order = await session.get(StarsBusinessOrder, order_id)
    if not order:
        return None
    order.status = "paid"
    order.paid_at = utcnow()
    await session.flush()
    return order


async def get_order_by_payload(session: AsyncSession, payload: str) -> StarsBusinessOrder | None:
    raw = (payload or "").strip()
    if not raw.isdigit():
        return None
    return await session.get(StarsBusinessOrder, int(raw))
