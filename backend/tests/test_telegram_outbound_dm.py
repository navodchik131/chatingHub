"""Tests for Telegram channel DM outbound send fallbacks."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.services.chat_outbound import send_telegram_outbound


def test_send_photo_falls_back_to_message_thread_id(monkeypatch):
    calls: list[dict] = []

    class _FakeBot:
        def __init__(self, *args, **kwargs):
            pass

        async def send_photo(self, **kwargs):
            calls.append(kwargs)
            if kwargs.get("direct_messages_topic_id") == 42:
                from aiogram.exceptions import TelegramBadRequest

                raise TelegramBadRequest(method="sendPhoto", message="bad topic")
            return SimpleNamespace(message_id=9001)

        @property
        def session(self):
            class _S:
                async def close(self):
                    return None

            return _S()

    monkeypatch.setattr("app.services.chat_outbound.Bot", _FakeBot)

    mid = asyncio.run(
        send_telegram_outbound(
            token="tok",
            chat_id=-1001,
            topic_id=42,
            text="",
            image_bytes=b"fake",
            image_mime="image/jpeg",
        )
    )

    assert mid == 9001
    assert calls[0].get("direct_messages_topic_id") == 42
    assert calls[1].get("message_thread_id") == 42
