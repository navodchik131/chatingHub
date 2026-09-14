"""Stars Business: окно 24ч и forward."""

from datetime import datetime, timedelta, timezone

from app.connectors.telegram.stars_business.fan_window import chat_window_open, window_label


def test_chat_window_open_within_24h():
    now = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
    last = now - timedelta(hours=23)
    assert chat_window_open(last, now=now) is True
    assert "🟢" in window_label(True)


def test_chat_window_closed_after_24h():
    now = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
    last = now - timedelta(hours=25)
    assert chat_window_open(last, now=now) is False
    assert "🔴" in window_label(False)
