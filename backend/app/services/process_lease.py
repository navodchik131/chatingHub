"""Lease через app_meta — один активный worker на ключ (MTProto, и т.д.)."""

from __future__ import annotations

import os
import socket
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

_LEASE_PREFIX = "lease:"


def _holder_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def _parse_lease(value: str) -> tuple[str, datetime] | None:
    raw = (value or "").strip()
    if "|" not in raw:
        return None
    holder, exp_s = raw.split("|", 1)
    try:
        exp = datetime.fromisoformat(exp_s)
    except ValueError:
        return None
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return holder.strip(), exp


async def _ensure_app_meta_table(session: AsyncSession) -> None:
    await session.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS app_meta (
                key VARCHAR(64) PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )


async def try_acquire_process_lease(
    session: AsyncSession,
    key: str,
    *,
    ttl_seconds: int = 45,
) -> bool:
    """True если lease получен или продлён текущим процессом."""
    meta_key = f"{_LEASE_PREFIX}{key}"[:64]
    holder = _holder_id()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=max(5, ttl_seconds))
    await _ensure_app_meta_table(session)
    row = (
        await session.execute(
            text("SELECT value FROM app_meta WHERE key = :k"),
            {"k": meta_key},
        )
    ).fetchone()
    if row:
        parsed = _parse_lease(str(row[0]))
        if parsed is not None:
            existing_holder, existing_exp = parsed
            if existing_holder != holder and existing_exp > now:
                return False
    value = f"{holder}|{expires.isoformat()}"
    await session.execute(
        text(
            """
            INSERT INTO app_meta (key, value, updated_at)
            VALUES (:k, :v, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """
        ),
        {"k": meta_key, "v": value},
    )
    await session.commit()
    return True


async def release_process_lease(session: AsyncSession, key: str) -> None:
    meta_key = f"{_LEASE_PREFIX}{key}"[:64]
    holder = _holder_id()
    row = (
        await session.execute(
            text("SELECT value FROM app_meta WHERE key = :k"),
            {"k": meta_key},
        )
    ).fetchone()
    if not row:
        return
    parsed = _parse_lease(str(row[0]))
    if parsed is None or parsed[0] != holder:
        return
    await session.execute(text("DELETE FROM app_meta WHERE key = :k"), {"k": meta_key})
    await session.commit()
