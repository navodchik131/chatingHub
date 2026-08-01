"""Tests for Telegram channel DM routing helpers."""

from __future__ import annotations

from types import SimpleNamespace

from app.connectors.telegram.channel_dm import (
    channel_dm_has_ingestable_content,
    is_channel_dm_message,
    resolve_channel_dm_topic_id,
)


def _msg(**kwargs):
    defaults = {
        "text": None,
        "caption": None,
        "photo": None,
        "sticker": None,
        "animation": None,
        "video": None,
        "video_note": None,
        "document": None,
        "direct_messages_topic": None,
        "message_thread_id": None,
        "from_user": SimpleNamespace(id=12345),
        "chat": SimpleNamespace(is_direct_messages=True, id=-1001),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_thread_photo_is_channel_dm_with_content():
    message = _msg(message_thread_id=42, photo=[SimpleNamespace(file_id="p1")])
    assert is_channel_dm_message(message)
    assert channel_dm_has_ingestable_content(message)
    assert resolve_channel_dm_topic_id(message) == "42"


def test_thread_text_only_is_channel_dm():
    message = _msg(message_thread_id=7, text="hello")
    assert is_channel_dm_message(message)
    assert channel_dm_has_ingestable_content(message)


def test_direct_messages_topic_video():
    topic = SimpleNamespace(topic_id=99)
    message = _msg(direct_messages_topic=topic, video=SimpleNamespace(file_id="v1"))
    assert is_channel_dm_message(message)
    assert channel_dm_has_ingestable_content(message)
    assert resolve_channel_dm_topic_id(message) == "99"


def test_private_chat_not_channel_dm():
    message = _msg(
        chat=SimpleNamespace(is_direct_messages=False, id=123),
        text="hi",
    )
    assert not is_channel_dm_message(message)


def test_topic_fallback_from_sender_when_no_thread():
    message = _msg(photo=[SimpleNamespace(file_id="p1")])
    assert resolve_channel_dm_topic_id(message) == "12345"
    assert is_channel_dm_message(message)


def test_threadless_media_is_routed_as_channel_dm():
    message = _msg(sticker=SimpleNamespace(emoji="😀", file_id="s1"))
    assert is_channel_dm_message(message)
    assert channel_dm_has_ingestable_content(message)
