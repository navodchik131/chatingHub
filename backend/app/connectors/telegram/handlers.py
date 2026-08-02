from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import BaseFilter
from aiogram.types import Message, MessageReactionUpdated

from app.config import settings
from app.connectors.telegram.channel_dm import (
    channel_dm_has_ingestable_content,
    is_channel_dm_message,
)
from app.connectors.telegram.ingest import ingest_telegram_dm, ingest_telegram_message_reaction

log = logging.getLogger(__name__)

router = Router(name="telegram_channel_dm")


class ChannelDMIngestFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return is_channel_dm_message(message) and channel_dm_has_ingestable_content(message)


@router.message(ChannelDMIngestFilter())
async def on_channel_dm(message: Message) -> None:
    if settings.legacy_user_id <= 0:
        return
    source = "direct_messages_topic" if message.direct_messages_topic is not None else "message_thread_id"
    await ingest_telegram_dm(settings.legacy_user_id, message, source=source)


@router.message_reaction()
async def on_channel_dm_reaction(reaction: MessageReactionUpdated) -> None:
    if settings.legacy_user_id <= 0:
        return
    await ingest_telegram_message_reaction(
        settings.legacy_user_id,
        reaction,
        source="polling",
    )


@router.message(
    F.chat.is_direct_messages.is_(True),
    F.text | F.caption,
)
async def on_channel_dm_unroutable(message: Message) -> None:
    if message.direct_messages_topic is not None or message.message_thread_id is not None:
        return
    log.warning(
        "channel DM message without topic and message_thread_id chat_id=%s msg_id=%s",
        message.chat.id,
        message.message_id,
    )
