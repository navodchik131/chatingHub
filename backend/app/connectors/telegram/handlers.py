from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import BaseFilter
from aiogram.types import Message

from app.config import settings
from app.connectors.telegram.ingest import ingest_telegram_dm

log = logging.getLogger(__name__)

router = Router(name="telegram_channel_dm")


class ChannelDMFallbackFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if not (message.text or message.caption):
            return False
        if getattr(message.chat, "is_direct_messages", None) is not True:
            return False
        if message.direct_messages_topic is not None:
            return False
        return message.message_thread_id is not None


@router.message(F.direct_messages_topic, F.text | F.caption)
async def on_channel_direct_message(message: Message) -> None:
    if settings.legacy_user_id <= 0:
        return
    topic = message.direct_messages_topic
    if topic is None:
        return
    await ingest_telegram_dm(
        settings.legacy_user_id,
        message,
        source="direct_messages_topic",
    )


@router.message(ChannelDMFallbackFilter())
async def on_channel_dm_by_thread(message: Message) -> None:
    if settings.legacy_user_id <= 0:
        return
    tid = message.message_thread_id
    if tid is None:
        return
    await ingest_telegram_dm(
        settings.legacy_user_id,
        message,
        source="message_thread_id",
    )


@router.message(F.chat.is_direct_messages.is_(True), F.text | F.caption)
async def on_channel_dm_unroutable(message: Message) -> None:
    if message.direct_messages_topic is not None:
        return
    if message.message_thread_id is not None:
        return
    log.warning(
        "channel DM message without topic and message_thread_id chat_id=%s msg_id=%s",
        message.chat.id,
        message.message_id,
    )


@router.message(F.direct_messages_topic)
async def on_channel_dm_other(message: Message) -> None:
    log.debug("skip non-text DM message_id=%s", message.message_id)
