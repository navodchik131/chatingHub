from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import BaseFilter
from aiogram.types import Message

from app.db.models import MessageDirection, Platform
from app.db.repo import add_message, get_or_create_conversation
from app.db.session import SessionLocal
from app.schemas import MessageOut
from app.services.realtime import hub
from app.services.translation import translate_to_russian

log = logging.getLogger(__name__)

router = Router(name="telegram_channel_dm")


class ChannelDMFallbackFilter(BaseFilter):
    """
    Direct messages чата канала, но без поля direct_messages_topic в апдейте
    (иногда клиент/сервер отдаёт только message_thread_id).
    """

    async def __call__(self, message: Message) -> bool:
        if not (message.text or message.caption):
            return False
        if getattr(message.chat, "is_direct_messages", None) is not True:
            return False
        if message.direct_messages_topic is not None:
            return False
        return message.message_thread_id is not None


async def _ingest_dm(
    message: Message,
    topic_id_str: str,
    *,
    source: str,
) -> None:
    text = (message.text or message.caption or "").strip()
    if not text:
        return

    chat_id = str(message.chat.id)
    user = message.from_user
    display = None
    if user:
        parts = [user.first_name or "", user.last_name or ""]
        display = " ".join(p for p in parts if p).strip() or user.username
    if not display:
        display = f"user_{user.id if user else 'unknown'}"

    translated, src_lang = await translate_to_russian(text)

    async with SessionLocal() as session:
        conv = await get_or_create_conversation(
            session,
            Platform.telegram,
            chat_id,
            topic_id_str,
            display,
        )
        if not conv.user_lang:
            conv.user_lang = src_lang
        elif src_lang and src_lang != "unknown":
            conv.user_lang = src_lang
        conv.updated_at = datetime.now(timezone.utc)

        meta = json.dumps(
            {
                "message_id": message.message_id,
                "from_user_id": user.id if user else None,
                "ingest_source": source,
            },
            ensure_ascii=False,
        )
        row = await add_message(
            session,
            conv.id,
            MessageDirection.inbound,
            text,
            translated,
            meta=meta,
        )
        await session.commit()
        await session.refresh(row)

    event = {
        "type": "new_message",
        "conversation_id": conv.id,
        "message": MessageOut.model_validate(row).model_dump(mode="json"),
    }
    await hub.broadcast(event)
    log.info(
        "ingested telegram DM conv=%s topic=%s source=%s",
        conv.id,
        topic_id_str,
        source,
    )


@router.message(F.direct_messages_topic, F.text | F.caption)
async def on_channel_direct_message(message: Message) -> None:
    """Основной путь: в апдейте есть direct_messages_topic."""
    topic = message.direct_messages_topic
    if topic is None:
        return
    await _ingest_dm(message, str(topic.topic_id), source="direct_messages_topic")


@router.message(ChannelDMFallbackFilter())
async def on_channel_dm_by_thread(message: Message) -> None:
    """Запасной путь: топик только в message_thread_id."""
    tid = message.message_thread_id
    if tid is None:
        return
    await _ingest_dm(message, str(tid), source="message_thread_id")


@router.message(F.chat.is_direct_messages.is_(True), F.text | F.caption)
async def on_channel_dm_unroutable(message: Message) -> None:
    """Есть текст в DM-чате, но нет ни topic, ни thread — только в лог."""
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
    """Стикеры/медиа без подписи."""
    log.debug("skip non-text DM message_id=%s", message.message_id)
