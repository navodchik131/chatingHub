"""Долгоживущий worker MTProto: приём личных сообщений."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from telethon import events

from app.config import settings
from app.connectors.telegram_user.client import build_telegram_client, require_mtproto_config
from app.connectors.telegram_user.ingest import ingest_telegram_user_dm
from app.db.models import TelegramUserSession, TelegramUserSessionStatus
from app.db.session import SessionLocal

log = logging.getLogger(__name__)

_worker_refresh = asyncio.Event()
_running_clients: dict[int, object] = {}
_running_tasks: dict[int, asyncio.Task[None]] = {}


def request_telegram_user_worker_refresh() -> None:
    _worker_refresh.set()


def get_worker_client(session_id: int):
    client = _running_clients.get(session_id)
    if client is not None and getattr(client, "is_connected", lambda: False)():
        return client
    return None


async def _load_active_sessions() -> list[TelegramUserSession]:
    async with SessionLocal() as session:
        rows = list(
            (
                await session.scalars(
                    select(TelegramUserSession).where(
                        TelegramUserSession.is_active.is_(True),
                        TelegramUserSession.status == TelegramUserSessionStatus.active.value,
                        TelegramUserSession.session_encrypted.isnot(None),
                    )
                )
            ).all()
        )
        return rows


async def _stop_client(session_id: int) -> None:
    task = _running_tasks.pop(session_id, None)
    client = _running_clients.pop(session_id, None)
    if client is not None:
        try:
            await client.disconnect()
        except Exception:
            log.exception("telegram_user worker: disconnect failed session=%s", session_id)
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def _start_client(row: TelegramUserSession) -> None:
    if row.id in _running_clients:
        client = _running_clients[row.id]
        if getattr(client, "is_connected", lambda: False)():
            return
        await _stop_client(row.id)

    if not row.session_encrypted:
        return

    client = build_telegram_client(session_encrypted=row.session_encrypted)
    owner_id = row.user_id
    session_id = row.id
    studio_model_id = row.studio_model_id

    @client.on(events.NewMessage())
    async def _on_new_message(event: events.NewMessage.Event) -> None:
        if not event.is_private or event.out:
            return
        msg = event.message
        if not msg:
            return
        sender = await event.get_sender()
        try:
            await ingest_telegram_user_dm(
                owner_user_id=owner_id,
                session_row_id=session_id,
                studio_model_id=studio_model_id,
                message=msg,
                sender=sender,
                client=client,
            )
        except Exception:
            log.exception(
                "telegram_user worker ingest failed owner=%s session=%s",
                owner_id,
                session_id,
            )

    try:
        await client.start()
        if not await client.is_user_authorized():
            log.warning("telegram_user worker: session %s not authorized", session_id)
            await client.disconnect()
            async with SessionLocal() as session:
                db_row = await session.get(TelegramUserSession, session_id)
                if db_row:
                    db_row.status = TelegramUserSessionStatus.error.value
                    db_row.error_message = "Сессия недействительна — переподключите аккаунт."
                    db_row.updated_at = datetime.now(timezone.utc)
                    await session.commit()
            return

        _running_clients[session_id] = client
        me = await client.get_me()

        async def _pump() -> None:
            try:
                await client.run_until_disconnected()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("telegram_user worker pump ended session=%s", session_id)
            finally:
                _running_clients.pop(session_id, None)
                _running_tasks.pop(session_id, None)
                request_telegram_user_worker_refresh()

        _running_tasks[session_id] = asyncio.create_task(_pump())

        async with SessionLocal() as session:
            db_row = await session.get(TelegramUserSession, session_id)
            if db_row:
                db_row.last_seen_at = datetime.now(timezone.utc)
                if me:
                    db_row.telegram_user_id = int(me.id)
                    db_row.telegram_username = (me.username or "").strip() or None
                await session.commit()
        log.info(
            "telegram_user worker: started session=%s owner=%s @%s",
            session_id,
            owner_id,
            me.username if me else "?",
        )
    except Exception:
        log.exception("telegram_user worker: start failed session=%s", session_id)
        await _stop_client(session_id)


async def _sync_clients() -> None:
    if not settings.telegram_mtproto_configured:
        return
    active_rows = await _load_active_sessions()
    active_ids = {r.id for r in active_rows}
    for sid in list(_running_clients.keys()):
        if sid not in active_ids:
            await _stop_client(sid)
    for row in active_rows:
        existing = _running_clients.get(row.id)
        if existing is not None and getattr(existing, "is_connected", lambda: False)():
            continue
        if existing is not None:
            await _stop_client(row.id)
        await _start_client(row)


async def telegram_user_worker_loop() -> None:
    if not settings.telegram_user_worker_enabled:
        log.info("Telegram user MTProto worker disabled")
        return
    try:
        require_mtproto_config()
    except RuntimeError as e:
        log.warning("Telegram user MTProto worker not started: %s", e)
        return

    log.info("Telegram user MTProto worker started")
    await asyncio.sleep(3)
    while True:
        try:
            await _sync_clients()
        except Exception:
            log.exception("telegram_user worker sync failed")
        try:
            await asyncio.wait_for(_worker_refresh.wait(), timeout=20.0)
            _worker_refresh.clear()
        except asyncio.TimeoutError:
            pass


async def shutdown_telegram_user_worker() -> None:
    for sid in list(_running_clients.keys()):
        await _stop_client(sid)
