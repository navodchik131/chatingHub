"""Единая точка доступа к MTProto-клиенту сессии (worker + исходящие)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from telethon import TelegramClient

from app.connectors.telegram_user.client import build_telegram_client
from app.connectors.telegram_user.worker import (
    get_worker_client,
    request_telegram_user_worker_refresh,
)

log = logging.getLogger(__name__)

T = TypeVar("T")

_session_locks: dict[int, asyncio.Lock] = {}


def _lock_for(session_id: int) -> asyncio.Lock:
    lock = _session_locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _session_locks[session_id] = lock
    return lock


async def run_with_telegram_user_client(
    *,
    session_id: int,
    session_encrypted: str,
    operation: Callable[[TelegramClient], Awaitable[T]],
) -> T:
    """Выполнить операцию на worker-клиенте, если он подключён; иначе — кратковременно."""
    worker_client = get_worker_client(session_id)
    if worker_client is not None:
        async with _lock_for(session_id):
            live = get_worker_client(session_id)
            if live is not None and live.is_connected():
                return await operation(live)
            log.warning(
                "telegram_user worker client gone mid-lock session=%s — ephemeral fallback",
                session_id,
            )

    client = build_telegram_client(session_encrypted=session_encrypted)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("telegram user session not authorized")
        return await operation(client)
    finally:
        try:
            await client.disconnect()
        except Exception:
            log.exception("telegram_user ephemeral disconnect failed session=%s", session_id)
        request_telegram_user_worker_refresh()
