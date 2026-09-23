"""Долгоживущий worker MTProto: приём личных сообщений."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from telethon import events

from app.config import settings
from app.connectors.telegram_user.client import build_telegram_client, require_mtproto_config
from app.connectors.telegram_user.proxy import telethon_proxy_tuple
from app.connectors.telegram_user.ingest import ingest_telegram_user_dm
from app.db.models import TelegramUserSession, TelegramUserSessionStatus
from app.db.session import SessionLocal
from app.services.process_lease import try_acquire_process_lease

log = logging.getLogger(__name__)

_TELEGRAM_USER_LEASE_KEY = "telegram_user_worker"

_worker_refresh = asyncio.Event()
_running_clients: dict[int, object] = {}
_running_tasks: dict[int, asyncio.Task[None]] = {}
_heartbeat_tasks: dict[int, asyncio.Task[None]] = {}
# Сессии в процессе login — worker не должен держать тот же auth key
_login_blocked: set[int] = set()


def request_telegram_user_worker_refresh() -> None:
    _worker_refresh.set()


async def block_telegram_user_worker_session(session_id: int) -> None:
    """Остановить worker-клиент перед login/re-auth — иначе Telethon: disconnected."""
    _login_blocked.add(session_id)
    await _stop_client(session_id)
    request_telegram_user_worker_refresh()


def unblock_telegram_user_worker_session(session_id: int) -> None:
    _login_blocked.discard(session_id)
    request_telegram_user_worker_refresh()


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
    hb = _heartbeat_tasks.pop(session_id, None)
    if hb is not None:
        hb.cancel()
        try:
            await hb
        except asyncio.CancelledError:
            pass
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


async def _heartbeat_loop(session_id: int, client) -> None:
    """Пинг + catch_up: ловим «зомби»-соединения и пропущенные апдейты без 5‑мин задержки."""
    ticks = 0
    try:
        while session_id in _running_clients and _running_clients.get(session_id) is client:
            await asyncio.sleep(25)
            if session_id not in _running_clients:
                return
            if not getattr(client, "is_connected", lambda: False)():
                log.warning("telegram_user heartbeat: disconnected session=%s", session_id)
                break
            try:
                await asyncio.wait_for(client.get_me(), timeout=20)
            except Exception:
                log.warning("telegram_user heartbeat: ping failed session=%s", session_id)
                break
            ticks += 1
            if ticks >= 2:
                ticks = 0
                try:
                    await asyncio.wait_for(client.catch_up(), timeout=40)
                except Exception:
                    log.warning("telegram_user heartbeat: catch_up failed session=%s", session_id)
    except asyncio.CancelledError:
        raise
    finally:
        if session_id in _running_clients:
            log.warning("telegram_user heartbeat: forcing reconnect session=%s", session_id)
            asyncio.create_task(_stop_client(session_id))
            request_telegram_user_worker_refresh()


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
        # Подтянуть апдейты, пропущенные пока worker был offline.
        try:
            await client.catch_up()
        except Exception:
            log.exception("telegram_user worker catch_up failed session=%s", session_id)

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
        _heartbeat_tasks[session_id] = asyncio.create_task(_heartbeat_loop(session_id, client))

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
    started_this_sync = 0
    for row in active_rows:
        if row.id in _login_blocked:
            continue
        existing = _running_clients.get(row.id)
        if existing is not None and getattr(existing, "is_connected", lambda: False)():
            continue
        if existing is not None:
            await _stop_client(row.id)
        await _start_client(row)
        started_this_sync += 1
        # Не открываем 4 MTProto сразу — DC режет параллельные connect с одного IP.
        if started_this_sync < len(active_rows):
            await asyncio.sleep(4.0)

    connected = sum(
        1
        for row in active_rows
        if get_worker_client(row.id) is not None
    )
    proxy_on = telethon_proxy_tuple() is not None
    if connected < len(active_rows):
        log.warning(
            "telegram_user worker sync: active=%s connected=%s proxy=%s "
            "(если connected=0 — задайте TELEGRAM_PROXY или оставьте 1 active сессию)",
            len(active_rows),
            connected,
            "yes" if proxy_on else "no",
        )
    else:
        log.info(
            "telegram_user worker sync ok: active=%s connected=%s proxy=%s",
            len(active_rows),
            connected,
            "yes" if proxy_on else "no",
        )


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
    emfile_backoff_s = 0.0
    while True:
        if emfile_backoff_s > 0:
            log.warning(
                "telegram_user worker: backoff %.0fs after EMFILE (too many open files)",
                emfile_backoff_s,
            )
            await asyncio.sleep(emfile_backoff_s)
            emfile_backoff_s = 0.0
        try:
            async with SessionLocal() as session:
                has_lease = await try_acquire_process_lease(
                    session,
                    _TELEGRAM_USER_LEASE_KEY,
                    ttl_seconds=45,
                )
            if not has_lease:
                log.warning("telegram_user worker: another process holds lease, skip sync")
            else:
                await _sync_clients()
        except OSError as e:
            if getattr(e, "errno", None) == 24:
                emfile_backoff_s = 120.0
                log.error(
                    "telegram_user worker sync: EMFILE — pause reconnects so HTTP api is not starved"
                )
            else:
                log.exception("telegram_user worker sync failed (OSError)")
        except Exception:
            log.exception("telegram_user worker sync failed")
        active_rows = await _load_active_sessions()
        connected = sum(1 for row in active_rows if get_worker_client(row.id) is not None)
        # Не долбить connect каждые 2 с при недоступном DC — иначе сокеты копятся.
        wait_s = 30.0 if connected < len(active_rows) else 5.0
        try:
            await asyncio.wait_for(_worker_refresh.wait(), timeout=wait_s)
            _worker_refresh.clear()
        except asyncio.TimeoutError:
            pass


async def shutdown_telegram_user_worker() -> None:
    for sid in list(_running_clients.keys()):
        await _stop_client(sid)
