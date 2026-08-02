"""Helpers for Telegram channel direct messages (Bot API)."""

from __future__ import annotations

from aiogram.types import Message


def _document_is_media(message: Message) -> bool:
    doc = message.document
    if doc is None:
        return False
    mime = (doc.mime_type or "").lower()
    return mime.startswith("image/") or mime.startswith("video/")


def _chat_is_direct_messages_inbox(chat) -> bool:
    if getattr(chat, "is_direct_messages", None) is True:
        return True
    # Bot API иногда не проставляет is_direct_messages на media-апдейтах.
    if getattr(chat, "type", None) == "channel" and (getattr(chat, "id", 0) or 0) < 0:
        return True
    return False


def channel_dm_has_ingestable_content(message: Message) -> bool:
    if (message.text or message.caption or "").strip():
        return True
    if (
        message.photo
        or message.sticker
        or message.animation
        or message.video
        or message.video_note
        or _document_is_media(message)
    ):
        return True
    return False


def is_channel_dm_message(message: Message) -> bool:
    if message.direct_messages_topic is not None:
        return True
    if message.message_thread_id is not None and _chat_is_direct_messages_inbox(message.chat):
        return True
    if _chat_is_direct_messages_inbox(message.chat):
        if message.message_thread_id is not None:
            return True
        return message.from_user is not None and channel_dm_has_ingestable_content(message)
    return False


def resolve_channel_dm_topic_id(message: Message) -> str | None:
    if message.direct_messages_topic is not None:
        return str(message.direct_messages_topic.topic_id)
    if message.message_thread_id is not None:
        return str(message.message_thread_id)
    from_user = message.from_user
    if _chat_is_direct_messages_inbox(message.chat) and from_user is not None:
        return str(from_user.id)
    return None


def canonical_channel_dm_thread_id(message: Message) -> str | None:
    """Real thread/topic id when present (not peer-user fallback)."""
    if message.direct_messages_topic is not None:
        return str(message.direct_messages_topic.topic_id)
    if message.message_thread_id is not None:
        return str(message.message_thread_id)
    return None


def media_fallback_text(message: Message) -> str | None:
    if message.sticker:
        return (message.sticker.emoji or "").strip() or "🎭"
    if message.photo:
        return "📷 Фото"
    if message.video or message.animation:
        return "🎬 Видео"
    if message.video_note:
        return "🎥 Кружок"
    if _document_is_media(message):
        return "📎 Медиа"
    return None
