"""Апдейты Business: connection, входящие фаны, оплата."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import Router
from aiogram.types import BusinessConnection, Message, PaidMediaPurchased, Update

from app.connectors.telegram.stars_business.repo import (
    get_active_connection,
    get_connection_by_connection_id,
    get_order_by_payload,
    mark_order_paid,
    upsert_business_connection,
    upsert_fan_inbound,
)
from app.db.session import SessionLocal

log = logging.getLogger(__name__)

router = Router(name="stars_business_updates")


def collect_business_inbox_messages(upd: Update) -> list[Message]:
    """Все варианты апдейта с business_connection_id (на случай другого поля в Update)."""
    candidates: list[Message | None] = [
        upd.business_message,
        upd.edited_business_message,
        upd.message if upd.message and (upd.message.business_connection_id or "").strip() else None,
        upd.edited_message
        if upd.edited_message and (upd.edited_message.business_connection_id or "").strip()
        else None,
    ]
    seen: set[int] = set()
    out: list[Message] = []
    for msg in candidates:
        if msg is None:
            continue
        mid = int(msg.message_id)
        if mid in seen:
            continue
        seen.add(mid)
        out.append(msg)
    return out


async def apply_business_connection(connection: BusinessConnection) -> None:
    """Сохранить business_connection в БД (webhook + aiogram handler)."""
    owner = connection.user
    if owner is None:
        log.warning("stars business connection without user id=%s", connection.id)
        return
    async with SessionLocal() as session:
        await upsert_business_connection(
            session,
            owner_tg_user_id=int(owner.id),
            connection_id=connection.id,
            is_enabled=bool(connection.is_enabled),
            owner_user_chat_id=int(connection.user_chat_id),
        )
        await session.commit()
    rights = connection.rights
    log.info(
        "stars business connection owner=%s enabled=%s connection_id=%s rights=%s",
        owner.id,
        connection.is_enabled,
        connection.id,
        rights.model_dump(exclude_none=True) if rights is not None else None,
    )


@router.business_connection()
async def on_business_connection(connection: BusinessConnection) -> None:
    try:
        await apply_business_connection(connection)
    except Exception:
        log.exception("stars business connection handler failed")


def _inbound_dt(message: Message) -> datetime:
    if message.date:
        return datetime.fromtimestamp(int(message.date), tz=timezone.utc)
    return datetime.now(timezone.utc)


async def apply_business_message_cache(message: Message) -> None:
    """Кэш фана для /chats и /paid — только входящие от фана (не исходящие OWNER)."""
    bcid = (message.business_connection_id or "").strip()
    if not bcid:
        log.debug("stars business message skip: no business_connection_id")
        return
    if not message.from_user:
        log.debug("stars business message skip: no from_user")
        return
    if message.from_user.is_bot:
        return
    # Bot API Message не имеет out; исходящие от OWNER через бота — sender_business_bot.
    if getattr(message, "sender_business_bot", None) is not None:
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
        conn_row = await get_connection_by_connection_id(session, bcid)
        if conn_row is None:
            # Этап 1: один OWNER — если id в апдейте сменился, привязываем к активной записи.
            conn_row = await get_active_connection(session)
            if conn_row is not None and conn_row.connection_id != bcid:
                log.warning(
                    "stars business message: connection_id mismatch db=%s msg=%s — sync",
                    conn_row.connection_id,
                    bcid,
                )
                conn_row.connection_id = bcid
                await session.flush()
        if conn_row is None:
            log.warning(
                "stars business message skip: no OWNER in DB (fan_chat=%s bcid=%s) — "
                "OWNER должен подключить бота в Business",
                fan_chat_id,
                bcid,
            )
            return
        if not conn_row.is_enabled:
            log.warning("stars business message skip: business disabled owner=%s", conn_row.owner_tg_user_id)
            return
        if int(message.from_user.id) == int(conn_row.owner_tg_user_id):
            return
        await upsert_fan_inbound(
            session,
            owner_tg_user_id=int(conn_row.owner_tg_user_id),
            fan_chat_id=fan_chat_id,
            fan_display_name=name or None,
            inbound_at=_inbound_dt(message),
        )
        await session.commit()
    log.info(
        "stars business fan cached owner=%s fan_chat=%s name=%s",
        conn_row.owner_tg_user_id,
        fan_chat_id,
        name or "?",
    )


@router.business_message()
async def on_business_message(message: Message) -> None:
    try:
        await apply_business_message_cache(message)
    except Exception:
        log.exception("stars business_message handler failed")


@router.edited_business_message()
async def on_edited_business_message(message: Message) -> None:
    try:
        await apply_business_message_cache(message)
    except Exception:
        log.exception("stars edited_business_message handler failed")


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
