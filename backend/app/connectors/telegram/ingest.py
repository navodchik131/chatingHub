"""Приём сообщений Telegram DM в аккаунт пользователя (SaaS + legacy)."""

from __future__ import annotations

import json
import logging

from aiogram.types import Message

from app.connectors.telegram.bot_for_user import (
    open_telegram_bot_for_owner,
    telegram_profile_photo_file_id,
)
from app.connectors.telegram.media import download_telegram_image
from app.db.models import Platform
from app.db.repo import get_or_create_conversation, get_user_with_billing
from app.db.session import SessionLocal
from app.services.chat_ingest import persist_inbound_chat_message
from app.services.translation import translate_to_russian

log = logging.getLogger(__name__)


async def ingest_telegram_dm(
    owner_user_id: int,
    message: Message,
    *,
    source: str,
) -> None:
    text = (message.text or message.caption or "").strip()
    has_photo = bool(message.photo) or (
        message.document is not None
        and (message.document.mime_type or "").lower().startswith("image/")
    )
    if not text and not has_photo:
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

        translated, src_lang = await translate_to_russian(text) if text else ("", None)

        photo_fid: str | None = None
        image_bytes: bytes | None = None
        image_mime: str | None = None
        bot, close_bot = await open_telegram_bot_for_owner(session, owner_user_id)
        try:
            if bot and from_user:
                photo_fid = await telegram_profile_photo_file_id(bot, from_user.id)
            if bot and has_photo:
                img = await download_telegram_image(message, bot)
                if img:
                    image_bytes, image_mime = img
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

        meta = json.dumps(
            {
                "message_id": message.message_id,
                "from_user_id": from_user.id if from_user else None,
                "ingest_source": source,
                "has_image": bool(image_bytes),
            },
            ensure_ascii=False,
        )
        conv_id, _ = await persist_inbound_chat_message(
            session,
            owner_user_id=owner_user_id,
            conv=conv,
            display=display or "Telegram",
            text_original=text,
            text_translated=translated if text else None,
            src_lang=src_lang,
            meta=meta,
            image_bytes=image_bytes,
            image_mime=image_mime,
        )
        await session.commit()

    log.info(
        "ingested telegram DM user=%s conv=%s topic=%s source=%s image=%s",
        owner_user_id,
        conv_id,
        topic_id_str,
        source,
        bool(image_bytes),
    )
