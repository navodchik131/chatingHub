"""24-часовое окно ответа business-бота (can_reply)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

REPLY_WINDOW = timedelta(hours=24)


def chat_window_open(last_inbound_at: datetime, *, now: datetime | None = None) -> bool:
    ref = now or datetime.now(timezone.utc)
    ts = last_inbound_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ref - ts <= REPLY_WINDOW


def window_label(open_: bool) -> str:
    return "🟢 окно открыто" if open_ else "🔴 окно закрыто (>24ч без входящих)"
