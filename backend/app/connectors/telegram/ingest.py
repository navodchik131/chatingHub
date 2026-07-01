"""Приём сообщений Telegram DM в аккаунт пользователя (SaaS + legacy)."""

from __future__ import annotations

import json
import logging

from aiogram.types import Message as TelegramMessage
from aiogram.types import MessageReactionUpdated, ReactionTypeEmoji
from sqlalchemy import select

from app.connectors.telegram.bot_for_user import (
    open_telegram_bot_for_owner,
    telegram_profile_photo_file_id,
)
from app.connectors.telegram.media import download_telegram_image
from app.db.models import Conversation, Message, Platform
from app.db.repo import get_or_create_conversation, get_user_with_billing
from app.db.session import SessionLocal
from app.services.chat_ingest import broadcast_message_updated, persist_inbound_chat_message
from app.services.chat_message_meta import (
    REACTION_EMOJIS,
    parse_reactions,
    platform_message_id_from_meta,
    reactions_to_json,
    sync_actor_reactions,
)
from app.services.translation import translate_to_russian
from app.services.companion_bot.schedule import schedule_companion_reply

log = logging.getLogger(__name__)


def _telegram_reaction_emojis(reaction_types: list | None) -> list[str]:
    out: list[str] = []
    for rt in reaction_types or []:
        emoji: str | None = None
        if isinstance(rt, ReactionTypeEmoji):
            emoji = rt.emoji
        elif isinstance(rt, dict):
            emoji = str(rt.get("emoji") or "").strip() or None
        else:
            emoji = getattr(rt, "emoji", None)
        if emoji and emoji in REACTION_EMOJIS and emoji not in out:
            out.append(emoji)
    return out


async def _find_telegram_message_in_chat(
    session,
    *,
    owner_user_id: int,
    chat_id: str,
    telegram_message_id: str,
) -> tuple[Message, Conversation] | None:
    stmt = (
        select(Message, Conversation)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.user_id == owner_user_id,
            Conversation.platform == Platform.telegram,
            Conversation.external_chat_id == chat_id,
        )
    )
    for msg, conv in (await session.execute(stmt)).all():
        pid = msg.platform_message_id or platform_message_id_from_meta(msg.meta)
        if pid == telegram_message_id:
            return msg, conv
    return None


async def ingest_telegram_message_reaction(
    owner_user_id: int,
    reaction: MessageReactionUpdated,
    *,
    source: str,
) -> None:
    chat_id = str(reaction.chat.id)
    tg_msg_id = str(reaction.message_id)
    new_emojis = _telegram_reaction_emojis(reaction.new_reaction)

    async with SessionLocal() as session:
        found = await _find_telegram_message_in_chat(
            session,
            owner_user_id=owner_user_id,
            chat_id=chat_id,
            telegram_message_id=tg_msg_id,
        )
        if not found:
            log.debug(
                "telegram reaction: message not found chat=%s msg=%s source=%s",
                chat_id,
                tg_msg_id,
                source,
            )
            return

        row, conv = found
        user = reaction.user
        if user is None:
            # Реакция бота (setMessageReaction) — уже синхронизирована через API.
            log.debug("telegram reaction: no user (bot echo), skip chat=%s msg=%s", chat_id, tg_msg_id)
            return

        fan_id = conv.external_topic_id
        actor = "peer" if str(user.id) == fan_id else "owner"
        reactions = sync_actor_reactions(
            parse_reactions(row.reactions_json),
            actor=actor,
            emojis=new_emojis,
        )
        row.reactions_json = reactions_to_json(reactions)
        await session.commit()
        await session.refresh(row, attribute_names=["attachments"])
        await broadcast_message_updated(
            session,
            owner_user_id=owner_user_id,
            conv_id=conv.id,
            row=row,
        )
        log.info(
            "ingested telegram reaction user=%s chat=%s msg=%s actor=%s emojis=%s source=%s",
            owner_user_id,
            chat_id,
            tg_msg_id,
            actor,
            new_emojis,
            source,
        )


async def ingest_telegram_dm(
    owner_user_id: int,
    message: TelegramMessage,
    *,
    source: str,
    telegram_connection_id: int | None = None,
    studio_model_id: int | None = None,
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

        photo_fid: str | None = None
        image_bytes: bytes | None = None
        image_mime: str | None = None
        bot, close_bot = await open_telegram_bot_for_owner(
            session, owner_user_id, telegram_connection_id=telegram_connection_id
        )
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
            telegram_connection_id=telegram_connection_id,
            studio_model_id=studio_model_id,
        )

        if text and not conv.auto_translate_disabled:
            translated, src_lang = await translate_to_russian(text)
        else:
            translated, src_lang = "", None

        reply_to_message_id: int | None = None
        if message.reply_to_message and message.reply_to_message.message_id:
            parent = await session.scalar(
                select(Message).where(
                    Message.conversation_id == conv.id,
                    Message.platform_message_id == str(message.reply_to_message.message_id),
                )
            )
            if parent:
                reply_to_message_id = parent.id

        meta = json.dumps(
            {
                "message_id": message.message_id,
                "from_user_id": from_user.id if from_user else None,
                "ingest_source": source,
                "has_image": bool(image_bytes),
            },
            ensure_ascii=False,
        )
        conv_id, payload = await persist_inbound_chat_message(
            session,
            owner_user_id=owner_user_id,
            conv=conv,
            display=display or "Telegram",
            text_original=text,
            text_translated=translated if text and not conv.auto_translate_disabled else None,
            src_lang=src_lang,
            meta=meta,
            image_bytes=image_bytes,
            image_mime=image_mime,
            reply_to_message_id=reply_to_message_id,
            platform_message_id=str(message.message_id),
        )
        if payload is None:
            return
        trigger_message_id = int(payload["id"])
        await session.commit()

    schedule_companion_reply(
        owner_user_id=owner_user_id,
        conv_id=conv_id,
        trigger_message_id=trigger_message_id,
    )

    log.info(
        "ingested telegram DM user=%s conv=%s topic=%s source=%s image=%s",
        owner_user_id,
        conv_id,
        topic_id_str,
        source,
        bool(image_bytes),
    )
