"""Фоновый запуск companion bot после входящего сообщения."""

from __future__ import annotations

import asyncio
import logging

from app.db.session import SessionLocal
from app.services.companion_bot.job_queue import (
    enqueue_companion_followup,
    enqueue_companion_reply,
)

log = logging.getLogger(__name__)


async def _enqueue_reply(
    *,
    owner_user_id: int,
    conv_id: int,
    trigger_message_id: int,
) -> None:
    async with SessionLocal() as session:
        await enqueue_companion_reply(
            session,
            owner_user_id=owner_user_id,
            conv_id=conv_id,
            trigger_message_id=trigger_message_id,
        )
        await session.commit()


async def _enqueue_followup(
    *,
    owner_user_id: int,
    conv_id: int,
    after_outbound_message_id: int,
) -> None:
    async with SessionLocal() as session:
        await enqueue_companion_followup(
            session,
            owner_user_id=owner_user_id,
            conv_id=conv_id,
            after_outbound_message_id=after_outbound_message_id,
        )
        await session.commit()


def schedule_companion_reply(
    *,
    owner_user_id: int,
    conv_id: int,
    trigger_message_id: int,
) -> None:
    log.info(
        "companion scheduled conv=%s trigger=%s owner=%s",
        conv_id,
        trigger_message_id,
        owner_user_id,
    )

    async def _run() -> None:
        try:
            await _enqueue_reply(
                owner_user_id=owner_user_id,
                conv_id=conv_id,
                trigger_message_id=trigger_message_id,
            )
        except Exception:
            log.exception(
                "companion enqueue failed conv=%s msg=%s",
                conv_id,
                trigger_message_id,
            )

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        asyncio.run(_run())


def schedule_companion_followup(
    *,
    owner_user_id: int,
    conv_id: int,
    after_outbound_message_id: int,
) -> None:
    async def _run() -> None:
        try:
            await _enqueue_followup(
                owner_user_id=owner_user_id,
                conv_id=conv_id,
                after_outbound_message_id=after_outbound_message_id,
            )
        except Exception:
            log.exception(
                "companion followup enqueue failed conv=%s outbound=%s",
                conv_id,
                after_outbound_message_id,
            )

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        asyncio.run(_run())
