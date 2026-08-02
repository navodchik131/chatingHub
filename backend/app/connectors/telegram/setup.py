import logging

from aiogram import Dispatcher
from aiogram.types import Update

from app.connectors.telegram.handlers import router as tg_router

log = logging.getLogger("telegram.incoming")

dp = Dispatcher()
dp.include_router(tg_router)


@dp.update.outer_middleware()
async def _log_incoming_updates(handler, event: Update, data: dict):
    """В логах видно, приходят ли апдейты и какие поля заполнены (отладка)."""
    if event.message:
        m = event.message
        log.info(
            "update.message chat_id=%s chat_type=%s is_direct_messages=%s "
            "direct_messages_topic=%s message_thread_id=%s from_id=%s "
            "text_len=%s has_photo=%s has_sticker=%s has_video=%s",
            m.chat.id,
            m.chat.type,
            getattr(m.chat, "is_direct_messages", None),
            m.direct_messages_topic,
            m.message_thread_id,
            m.from_user.id if m.from_user else None,
            len((m.text or m.caption or "")),
            bool(m.photo),
            bool(m.sticker),
            bool(m.video or m.animation or m.video_note),
        )
    elif event.message_reaction:
        r = event.message_reaction
        log.info(
            "update.message_reaction chat_id=%s msg_id=%s user_id=%s",
            r.chat.id,
            r.message_id,
            r.user.id if r.user else None,
        )
    elif event.edited_message:
        log.info("update.edited_message (ignored by app)")
    return await handler(event, data)
