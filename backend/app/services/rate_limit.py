"""Простой in-memory rate limiter для auth-эндпоинтов (на процесс)."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from fastapi import HTTPException, Request

from app.services.device_signal import client_ip_from_request

_buckets: dict[str, list[float]] = defaultdict(list)
_lock = asyncio.Lock()


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
    now = time.monotonic()
    async with _lock:
        cutoff = now - window_seconds
        recent = [t for t in _buckets[key] if t > cutoff]
        if len(recent) >= max_calls:
            raise HTTPException(
                status_code=429,
                detail="Слишком много запросов. Попробуйте позже.",
            )
        recent.append(now)
        _buckets[key] = recent
