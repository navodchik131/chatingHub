"""Tests for Telegram reaction sync."""

from __future__ import annotations

import asyncio

from app.services.chat_outbound import set_telegram_message_reaction


def test_set_telegram_message_reaction_uses_dm_topic_first(monkeypatch):
    calls: list[dict] = []

    class _FakeBot:
        def __init__(self, *args, **kwargs):
            pass

        async def set_message_reaction(self, **kwargs):
            calls.append({"method": "aiogram", **kwargs})
            raise RuntimeError("should not reach aiogram")

        @property
        def session(self):
            class _S:
                async def close(self):
                    return None

            return _S()

    async def _fake_raw(**kwargs):
        calls.append({"method": "raw", **kwargs})
        if kwargs.get("extra") == {"direct_messages_topic_id": 42}:
            return None
        raise RuntimeError("fallback failed")

    monkeypatch.setattr("app.services.chat_outbound.Bot", _FakeBot)
    monkeypatch.setattr("app.services.chat_outbound._raw_telegram_set_message_reaction", _fake_raw)

    ok = asyncio.run(
        set_telegram_message_reaction(
            token="test-token",
            chat_id=100,
            telegram_message_id=200,
            emoji="❤️",
            topic_id=42,
        )
    )

    assert ok is True
    assert calls[0]["method"] == "raw"
    assert calls[0]["extra"] == {"direct_messages_topic_id": 42}
    assert not any(c["method"] == "aiogram" for c in calls)


def test_set_telegram_message_reaction_plain_without_topic(monkeypatch):
    calls: list[dict] = []

    class _FakeBot:
        def __init__(self, *args, **kwargs):
            pass

        async def set_message_reaction(self, **kwargs):
            calls.append({"method": "aiogram", **kwargs})
            return True

        @property
        def session(self):
            class _S:
                async def close(self):
                    return None

            return _S()

    async def _fake_raw(**kwargs):
        calls.append({"method": "raw", **kwargs})
        if kwargs.get("extra") == {}:
            return None
        raise RuntimeError("unexpected extra")

    monkeypatch.setattr("app.services.chat_outbound.Bot", _FakeBot)
    monkeypatch.setattr("app.services.chat_outbound._raw_telegram_set_message_reaction", _fake_raw)

    ok = asyncio.run(
        set_telegram_message_reaction(
            token="test-token",
            chat_id=100,
            telegram_message_id=200,
            emoji="👍",
            topic_id=None,
        )
    )

    assert ok is True
    assert calls[0]["method"] == "raw"
    assert calls[0]["extra"] == {}
