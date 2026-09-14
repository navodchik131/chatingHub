"""Апдейты Business: connection, входящие фаны, оплата."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import Router
from aiogram.types import BusinessConnection, Message, PaidMediaPurchased

from app.connectors.telegram.stars_business.repo import (
    get_connection_by_connection_id,
    get_order_by_payload,
    mark_order_paid,
    upsert_business_connection,
    upsert_fan_inbound,
)
from app.db.session import SessionLocal

log = logging.getLogger(__name__)

router = Router(name="stars_business_updates")


@router.business_connection()
async def on_business_connection(connection: BusinessConnection) -> None:
    owner = connection.user
    async with SessionLocal() as session:
        await upsert_business_connection(
            session,
            owner_tg_user_id=int(owner.id),
            connection_id=connection.id,
            is_enabled=bool(connection.is_enabled),
            owner_user_chat_id=int(connection.user_chat_id),
        )
        await session.commit()
    log.info(
        "stars business connection owner=%s enabled=%s",
        owner.id,
        connection.is_enabled,
    )


def _inbound_dt(message: Message) -> datetime:
    if message.date:
        return datetime.fromtimestamp(int(message.date), tz=timezone.utc)
    return datetime.now(timezone.utc)


async def _cache_fan_message(message: Message) -> None:
    if not message.business_connection_id or not message.from_user:
        return
    if message.from_user.is_bot:
        return
    fan_chat_id = int(message.chat.id)
    name = " ".join(
        x
        for x in [
            message.from_user.first_name,
            message.from_user.last_name,
            f"@{message.from_user.username}" if message.from_user.username else None,
        ]
        if x
    ).strip()
    async with SessionLocal() as session:
        conn_row = await get_connection_by_connection_id(session, message.business_connection_id)
        if not conn_row or not conn_row.is_enabled:
            return
        await upsert_fan_inbound(
            session,
            owner_tg_user_id=int(conn_row.owner_tg_user_id),
            fan_chat_id=fan_chat_id,
            fan_display_name=name or None,
            inbound_at=_inbound_dt(message),
        )
        await session.commit()


@router.business_message()
async def on_business_message(message: Message) -> None:
    await _cache_fan_message(message)


@router.edited_business_message()
async def on_edited_business_message(message: Message) -> None:
    await _cache_fan_message(message)


@router.purchased_paid_media()
async def on_purchased_paid_media(ppm: PaidMediaPurchased) -> None:
    payload = (ppm.paid_media_payload or "").strip()
    if not payload:
        log.info("stars business purchase without payload user=%s", ppm.from_user.id if ppm.from_user else None)
        return
    oid: int | None = None
    async with SessionLocal() as session:
        order = await get_order_by_payload(session, payload)
        if not order:
            log.warning("stars business purchase unknown payload=%s", payload)
            return
        if order.status == "paid":
            await session.commit()
            return
        oid = order.id
        await mark_order_paid(session, oid)
        await session.commit()
    if oid is not None:
        log.info("stars business order paid id=%s payload=%s", oid, payload)
