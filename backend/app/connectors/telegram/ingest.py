"""Приём сообщений Telegram DM в аккаунт пользователя (SaaS + legacy)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from aiogram.types import Message

from app.connectors.telegram.bot_for_user import (
    open_telegram_bot_for_owner,
    telegram_profile_photo_file_id,
)
from app.db.models import MessageDirection, Platform
from app.db.repo import (
    add_message,
    get_or_create_conversation,
    get_user_with_billing,
)
from app.db.session import SessionLocal
from app.schemas import MessageOut
from app.services.realtime import hub
from app.services.translation import translate_to_russian

log = logging.getLogger(__name__)


async def ingest_telegram_dm(
    owner_user_id: int,
    message: Message,
    *,
    source: str,
) -> None:
    text = (message.text or message.caption or "").strip()
    if not text:
        return

    topic_id_str: str | None = None
    if message.direct_messages_topic is not None:
        topic_id_str = str(message.direct_messages_topic.topic_id)
    elif message.message_thread_id is not None:
        topic_id_str = str(message.message_thread_id)
    if topic_id_str is None:
        log.warning(
            "telegram ingest: no topic chat_id=%s msg_id=%s",
            message.chat.id,
            message.message_id,
        )
        return

    chat_id = str(message.chat.id)
    from_user = message.from_user
    display = None
    if from_user:
        parts = [from_user.first_name or "", from_user.last_name or ""]
        display = " ".join(p for p in parts if p).strip() or from_user.username
    if not display:
        display = f"user_{from_user.id if from_user else 'unknown'}"

    async with SessionLocal() as session:
        user = await get_user_with_billing(session, owner_user_id)
        if not user:
            log.warning("telegram ingest: user %s not found", owner_user_id)
            return

        translated, src_lang = await translate_to_russian(text)

        photo_fid: str | None = None
        bot, close_bot = await open_telegram_bot_for_owner(session, owner_user_id)
        try:
            if bot and from_user:
                photo_fid = await telegram_profile_photo_file_id(bot, from_user.id)
        finally:
            if close_bot and bot:
                await bot.session.close()

        conv = await get_or_create_conversation(
            session,
            owner_user_id,
            Platform.telegram,
            chat_id,
            topic_id_str,
            display,
            telegram_photo_file_id=photo_fid,
        )
        if not conv.user_lang:
            conv.user_lang = src_lang
        elif src_lang and src_lang != "unknown":
            conv.user_lang = src_lang
        conv.updated_at = datetime.now(timezone.utc)

        meta = json.dumps(
            {
                "message_id": message.message_id,
                "from_user_id": from_user.id if from_user else None,
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
        conv_id = conv.id
        payload = MessageOut.model_validate(row).model_dump(mode="json")

    await hub.broadcast_user(
        owner_user_id,
        {
            "type": "new_message",
            "conversation_id": conv_id,
            "message": payload,
        },
    )
    log.info(
        "ingested telegram DM user=%s conv=%s topic=%s source=%s",
        owner_user_id,
        conv_id,
        topic_id_str,
        source,
    )
