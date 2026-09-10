"""Rate limit auth/API: Postgres (multi-process) или in-memory fallback."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import SessionLocal
from app.services.device_signal import client_ip_from_request

_memory_buckets: dict[str, list[float]] = defaultdict(list)
_memory_lock = asyncio.Lock()


async def _enforce_rate_limit_memory(
    key: str,
    *,
    max_calls: int,
    window_seconds: float,
) -> None:
    now = time.monotonic()
    async with _memory_lock:
        cutoff = now - window_seconds
        recent = [t for t in _memory_buckets[key] if t > cutoff]
        if len(recent) >= max_calls:
            raise HTTPException(
                status_code=429,
                detail="Слишком много запросов. Попробуйте позже.",
            )
        recent.append(now)
        _memory_buckets[key] = recent


async def _enforce_rate_limit_postgres(
    bucket_key: str,
    *,
    max_calls: int,
    window_seconds: float,
) -> None:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=window_seconds)
    async with SessionLocal() as session:
        row = (
            await session.execute(
                text(
                    """
                    SELECT window_start, hit_count
                    FROM http_rate_limit_buckets
                    WHERE bucket_key = :key
                    """
                ),
                {"key": bucket_key[:128]},
            )
        ).fetchone()
        if row is None:
            await session.execute(
                text(
                    """
                    INSERT INTO http_rate_limit_buckets (bucket_key, window_start, hit_count)
                    VALUES (:key, :ws, 1)
                    """
                ),
                {"key": bucket_key[:128], "ws": now},
            )
            await session.commit()
            return
        ws = row[0]
        if ws.tzinfo is None:
            ws = ws.replace(tzinfo=timezone.utc)
        hits = int(row[1] or 0)
        if ws < window_start:
            await session.execute(
                text(
                    """
                    UPDATE http_rate_limit_buckets
                    SET window_start = :ws, hit_count = 1
                    WHERE bucket_key = :key
                    """
                ),
                {"key": bucket_key[:128], "ws": now},
            )
            await session.commit()
            return
        if hits >= max_calls:
            raise HTTPException(
                status_code=429,
                detail="Слишком много запросов. Попробуйте позже.",
            )
        await session.execute(
            text(
                """
                UPDATE http_rate_limit_buckets
                SET hit_count = hit_count + 1
                WHERE bucket_key = :key
                """
            ),
            {"key": bucket_key[:128]},
        )
        await session.commit()


async def enforce_rate_limit(
    request: Request,
    *,
    scope: str,
    max_calls: int,
    window_seconds: float,
) -> None:
    """429 если превышен лимит по IP + scope."""
    ip = client_ip_from_request(request) or "unknown"
    key = f"{scope}:{ip}"
    if settings.database_url.startswith("postgresql"):
        await _enforce_rate_limit_postgres(
            key,
            max_calls=max_calls,
            window_seconds=window_seconds,
        )
        return
    await _enforce_rate_limit_memory(
        key,
        max_calls=max_calls,
        window_seconds=window_seconds,
    )
