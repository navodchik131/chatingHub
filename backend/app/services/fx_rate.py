"""Курс USD/RUB с обновлением утром и вечером (МСК)."""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import httpx

log = logging.getLogger(__name__)

MSK = ZoneInfo("Europe/Moscow")
# Слоты обновления: 08:00 и 20:00 по Москве
_REFRESH_SLOTS = (time(8, 0), time(20, 0))
_FALLBACK_RUB_PER_USD = 90.0
_CBR_URL = "https://www.cbr-xml-daily.ru/daily_json.js"

_cache: dict[str, Any] = {
    "rub_per_usd": _FALLBACK_RUB_PER_USD,
    "updated_at": None,  # datetime | None
    "source": "fallback",
}


def _latest_slot(now: datetime) -> datetime:
    now_msk = now.astimezone(MSK)
    today = now_msk.date()
    yesterday: date = today - timedelta(days=1)
    candidates = [
        datetime.combine(today, slot, tzinfo=MSK) for slot in _REFRESH_SLOTS
    ]
    candidates.append(datetime.combine(yesterday, _REFRESH_SLOTS[-1], tzinfo=MSK))
    past = [c for c in candidates if c <= now_msk]
    return max(past)


def _needs_refresh(now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    updated = _cache.get("updated_at")
    if updated is None:
        return True
    if not isinstance(updated, datetime):
        return True
    return updated.astimezone(MSK) < _latest_slot(now)


async def _fetch_cbr_rub_per_usd() -> float:
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.get(_CBR_URL)
        r.raise_for_status()
        data = r.json()
    usd = (data.get("Valute") or {}).get("USD") or {}
    value = float(usd.get("Value") or 0)
    if value <= 0:
        raise ValueError("invalid CBR USD value")
    return value


async def get_usd_rate(*, force: bool = False) -> dict[str, Any]:
    """Возвращает { rub_per_usd, usd_per_rub, updated_at, source, next_refresh_at }."""
    now = datetime.now(timezone.utc)
    if force or _needs_refresh(now):
        try:
            rate = await _fetch_cbr_rub_per_usd()
            _cache["rub_per_usd"] = rate
            _cache["updated_at"] = now
            _cache["source"] = "cbr"
        except Exception as e:
            log.warning("fx usd fetch failed: %s", e)
            if _cache["updated_at"] is None:
                _cache["rub_per_usd"] = _FALLBACK_RUB_PER_USD
                _cache["updated_at"] = now
                _cache["source"] = "fallback"

    rub_per_usd = float(_cache["rub_per_usd"])
    updated = _cache["updated_at"] or now
    # следующий слот после now
    now_msk = now.astimezone(MSK)
    today = now_msk.date()
    tomorrow = today + timedelta(days=1)
    upcoming = [
        datetime.combine(today, slot, tzinfo=MSK) for slot in _REFRESH_SLOTS
    ] + [datetime.combine(tomorrow, _REFRESH_SLOTS[0], tzinfo=MSK)]
    next_slot = min(c for c in upcoming if c > now_msk)

    return {
        "rub_per_usd": round(rub_per_usd, 4),
        "usd_per_rub": round(1.0 / rub_per_usd, 8),
        "updated_at": updated.astimezone(timezone.utc).isoformat(),
        "source": _cache["source"],
        "next_refresh_at": next_slot.astimezone(timezone.utc).isoformat(),
    }
