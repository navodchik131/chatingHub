"""Stars Business: окно 24ч и forward."""

from datetime import datetime, timedelta, timezone

from aiogram.types import Chat, Message, User

from app.connectors.telegram.stars_business.fan_window import chat_window_open, window_label
from app.connectors.telegram.stars_business.handlers_business import _inbound_dt
from app.connectors.telegram.stars_business.media_storage import decode_media_paths, encode_media_paths


def test_chat_window_open_within_24h():
    now = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
    last = now - timedelta(hours=23)
    assert chat_window_open(last, now=now) is True
    assert "🟢" in window_label(True)


def test_encode_decode_album_paths():
    one = encode_media_paths(["owner/a.jpg"])
    assert one == "owner/a.jpg"
    assert decode_media_paths(one) == ["owner/a.jpg"]
    many = encode_media_paths(["owner/a.jpg", "owner/b.jpg"])
    assert decode_media_paths(many) == ["owner/a.jpg", "owner/b.jpg"]


def test_inbound_dt_accepts_aiogram_datetime():
    """Регрессия: int(message.date) падал на datetime от pydantic."""
    ts = datetime(2026, 3, 14, 10, 0, tzinfo=timezone.utc)
    msg = Message(
        message_id=1,
        date=ts,
        chat=Chat(id=99, type="private"),
        from_user=User(id=99, is_bot=False, first_name="Fan"),
        business_connection_id="bc-test",
    )
    assert _inbound_dt(msg) == ts


def test_chat_window_closed_after_24h():
    now = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
    last = now - timedelta(hours=25)
    assert chat_window_open(last, now=now) is False
    assert "🔴" in window_label(False)
