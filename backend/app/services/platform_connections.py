"""Несколько подключений Telegram/Fanvue на пользователя; модель на подключении."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Conversation,
    FanvueConnection,
    Platform,
    Subscription,
    TelegramConnection,
)
from app.services.billing_plan import is_credits_plan
from app.services.entitlements import subscription_is_paid_active
from app.services.plan_catalog import CREDITS_PLAN_LIMITS, plan_display_name
from app.services.workspace_model_access import validate_owner_studio_model_id


async def count_telegram_connections(session: AsyncSession, owner_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(TelegramConnection)
            .where(
                TelegramConnection.user_id == owner_id,
                TelegramConnection.is_active.is_(True),
            )
        )
        or 0
    )


async def count_fanvue_connections(session: AsyncSession, owner_id: int) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(FanvueConnection)
            .where(FanvueConnection.user_id == owner_id)
        )
        or 0
    )


async def assert_can_add_platform_connection(
    session: AsyncSession,
    owner_id: int,
    sub: Subscription | None,
    *,
    platform: Platform,
) -> None:
    """Лимит подключений к площадке = лимит моделей на тарифе."""
    lim = plan_limits_for_sub(sub)
    limits_on = True
    if sub is not None and is_credits_plan(sub.billing_plan) and not subscription_is_paid_active(sub):
        lim = CREDITS_PLAN_LIMITS
    elif sub is not None and subscription_is_paid_active(sub):
        limits_on = True
    elif sub is None or not subscription_is_paid_active(sub):
        if not (sub is not None and is_credits_plan(sub.billing_plan)):
            return

    if not limits_on and not (
        sub is not None and is_credits_plan(sub.billing_plan) and not subscription_is_paid_active(sub)
    ):
        return

    if platform == Platform.telegram:
        n = await count_telegram_connections(session, owner_id)
    else:
        n = await count_fanvue_connections(session, owner_id)
    if n >= lim.max_models:
        plat = "Telegram" if platform == Platform.telegram else "Fanvue"
        raise HTTPException(
            status_code=402,
            detail=(
                f"Достигнут лимит подключений {plat} ({lim.max_models}) для тарифа "
                f"{plan_display_name(sub.billing_plan if sub else None, sub.plan_tier if sub else None)}. "
                "Удалите лишнее подключение или повысьте план."
            ),
        )


async def validate_connection_studio_model(
    session: AsyncSession, owner_id: int, model_id: int | None
) -> None:
    await validate_owner_studio_model_id(session, owner_id, model_id)


def connection_studio_model_id(
    conn: TelegramConnection | FanvueConnection | None,
) -> int | None:
    if conn is None:
        return None
    return conn.studio_model_id


async def sync_conversations_model_from_connection(
    session: AsyncSession,
    *,
    platform: Platform,
    connection_id: int,
    studio_model_id: int | None,
) -> None:
    if platform == Platform.telegram:
        stmt = (
            update(Conversation)
            .where(Conversation.telegram_connection_id == connection_id)
            .values(studio_model_id=studio_model_id)
        )
    else:
        stmt = (
            update(Conversation)
            .where(Conversation.fanvue_connection_id == connection_id)
            .values(studio_model_id=studio_model_id)
        )
    await session.execute(stmt)


async def get_telegram_connection_for_owner(
    session: AsyncSession,
    owner_id: int,
    *,
    connection_id: int | None = None,
) -> TelegramConnection | None:
    if connection_id is not None:
        return await session.scalar(
            select(TelegramConnection).where(
                TelegramConnection.id == connection_id,
                TelegramConnection.user_id == owner_id,
                TelegramConnection.is_active.is_(True),
            )
        )
    return await session.scalar(
        select(TelegramConnection)
        .where(
            TelegramConnection.user_id == owner_id,
            TelegramConnection.is_active.is_(True),
        )
        .order_by(TelegramConnection.id.asc())
        .limit(1)
    )


async def get_fanvue_connection_for_owner(
    session: AsyncSession,
    owner_id: int,
    *,
    connection_id: int | None = None,
) -> FanvueConnection | None:
    if connection_id is not None:
        return await session.scalar(
            select(FanvueConnection).where(
                FanvueConnection.id == connection_id,
                FanvueConnection.user_id == owner_id,
            )
        )
    return await session.scalar(
        select(FanvueConnection)
        .where(FanvueConnection.user_id == owner_id)
        .order_by(FanvueConnection.id.asc())
        .limit(1)
    )


async def resolve_fanvue_connection_for_conversation(
    session: AsyncSession,
    conv: Conversation,
    owner_id: int,
) -> FanvueConnection | None:
    if conv.fanvue_connection_id:
        return await get_fanvue_connection_for_owner(
            session, owner_id, connection_id=conv.fanvue_connection_id
        )
    creator = (conv.external_topic_id or "").strip()
    if creator:
        row = await session.scalar(
            select(FanvueConnection).where(
                FanvueConnection.user_id == owner_id,
                FanvueConnection.creator_uuid == creator,
            )
        )
        if row:
            return row
    return await get_fanvue_connection_for_owner(session, owner_id)


async def resolve_telegram_connection_for_conversation(
    session: AsyncSession,
    conv: Conversation,
    owner_id: int,
) -> TelegramConnection | None:
    if conv.telegram_connection_id:
        return await get_telegram_connection_for_owner(
            session, owner_id, connection_id=conv.telegram_connection_id
        )
    return await get_telegram_connection_for_owner(session, owner_id)
