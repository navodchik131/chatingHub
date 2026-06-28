"""Оркестрация ответа companion bot."""

from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    BotResponseEvent,
    BotResponseEventStatus,
    CompanionBotMode,
    Conversation,
    Message,
    MessageDirection,
    Platform,
)
from app.db.repo import list_messages
from app.db.session import SessionLocal
from app.services.companion_bot.config import CompanionConnectionConfig, get_companion_config_for_conversation
from app.services.companion_bot.generate import generate_companion_reply
from app.services.companion_bot.prompt import PROMPT_VERSION, resolve_target_lang
from app.services.companion_bot.send import broadcast_companion_message, send_companion_outbound
from app.services.realtime import hub

log = logging.getLogger(__name__)


def _semi_auto_allowed(*, trigger: Message, has_image: bool) -> bool:
    if has_image:
        return False
    text = (trigger.text_original or "").strip()
    if not text:
        return False
    return len(text) <= 320


async def _count_recent_sends(
    session: AsyncSession,
    *,
    connection_id: int,
    platform: Platform,
    max_per_hour: int,
) -> bool:
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    q = (
        select(func.count())
        .select_from(BotResponseEvent)
        .join(Conversation, BotResponseEvent.conversation_id == Conversation.id)
        .where(
            BotResponseEvent.status == BotResponseEventStatus.sent,
            BotResponseEvent.sent_at >= since,
        )
    )
    if platform == Platform.telegram:
        q = q.where(Conversation.telegram_connection_id == connection_id)
    else:
        q = q.where(Conversation.fanvue_connection_id == connection_id)
    n = int(await session.scalar(q) or 0)
    return n < max_per_hour


async def _is_stale_trigger(
    session: AsyncSession, conv_id: int, trigger_message_id: int
) -> bool:
    latest = await session.scalar(
        select(Message.id)
        .where(
            Message.conversation_id == conv_id,
            Message.direction == MessageDirection.inbound,
        )
        .order_by(Message.id.desc())
        .limit(1)
    )
    return latest != trigger_message_id


async def _existing_event_for_trigger(
    session: AsyncSession, trigger_message_id: int
) -> BotResponseEvent | None:
    return await session.scalar(
        select(BotResponseEvent).where(
            BotResponseEvent.trigger_message_id == trigger_message_id,
            BotResponseEvent.status.in_(
                [BotResponseEventStatus.draft, BotResponseEventStatus.sent]
            ),
        )
    )


async def create_companion_reply_event(
    session: AsyncSession,
    *,
    owner_user_id: int,
    conv: Conversation,
    trigger_message_id: int,
    cfg: CompanionConnectionConfig,
) -> BotResponseEvent | None:
    trigger = await session.get(Message, trigger_message_id)
    if not trigger or trigger.conversation_id != conv.id:
        return None
    if trigger.direction != MessageDirection.inbound:
        return None

    if await _existing_event_for_trigger(session, trigger_message_id):
        return None

    await session.refresh(trigger, attribute_names=["attachments"])
    has_image = bool(trigger.attachments)
    if cfg.mode == CompanionBotMode.semi_auto and not _semi_auto_allowed(
        trigger=trigger, has_image=has_image
    ):
        return None

    if not cfg.studio_model_id:
        log.warning("companion bot: no studio_model on connection conv=%s", conv.id)
        return None

    if not await _count_recent_sends(
        session,
        connection_id=cfg.connection_id,
        platform=cfg.platform,
        max_per_hour=cfg.max_replies_per_hour,
    ):
        log.info("companion bot: rate limit connection=%s", cfg.connection_id)
        return None

    text_in = (trigger.text_original or "").strip()
    if not text_in and has_image:
        return None
    if not text_in:
        return None

    history = await list_messages(session, conv.id, owner_user_id, limit=50)
    target_lang = resolve_target_lang(conv)
    try:
        reply, lang, model_name, _, snapshot = await generate_companion_reply(
            session,
            owner_id=owner_user_id,
            conv=conv,
            messages=history,
            studio_model_id=cfg.studio_model_id,
        )
    except Exception as e:
        log.warning("companion generate failed conv=%s: %s", conv.id, e)
        fail = BotResponseEvent(
            conversation_id=conv.id,
            trigger_message_id=trigger_message_id,
            draft_text="",
            status=BotResponseEventStatus.failed,
            prompt_version=PROMPT_VERSION,
            persona_model_id=cfg.studio_model_id,
            target_lang=target_lang,
        )
        session.add(fail)
        await session.flush()
        return None

    event = BotResponseEvent(
        conversation_id=conv.id,
        trigger_message_id=trigger_message_id,
        draft_text=reply,
        status=BotResponseEventStatus.draft,
        prompt_version=PROMPT_VERSION,
        persona_model_id=cfg.studio_model_id,
        target_lang=lang,
        model_name=model_name,
        state_snapshot_json=json.dumps(snapshot, ensure_ascii=False),
    )
    session.add(event)
    await session.flush()
    return event


async def approve_and_send_companion_draft(
    session: AsyncSession,
    *,
    owner_user_id: int,
    conv: Conversation,
    event: BotResponseEvent,
    text_override: str | None = None,
) -> Message:
    if event.status != BotResponseEventStatus.draft:
        raise ValueError("event not in draft status")
    final_text = (text_override or event.draft_text or "").strip()
    if not final_text:
        raise ValueError("empty draft text")
    if text_override and text_override.strip() != (event.draft_text or "").strip():
        event.was_edited = True
        event.draft_text = final_text

    row = await send_companion_outbound(
        session,
        owner_id=owner_user_id,
        conv=conv,
        text=final_text,
        reply_to_message_id=event.trigger_message_id,
        bot_response_event_id=event.id,
    )
    event.status = BotResponseEventStatus.sent
    event.sent_text = final_text
    event.outbound_message_id = row.id
    event.sent_at = datetime.now(timezone.utc)
    return row


async def run_companion_pipeline(
    *,
    owner_user_id: int,
    conv_id: int,
    trigger_message_id: int,
) -> None:
    async with SessionLocal() as session:
        conv = await session.get(Conversation, conv_id)
        if not conv or conv.user_id != owner_user_id:
            return
        cfg = await get_companion_config_for_conversation(session, conv)
        if not cfg:
            return

        event = await create_companion_reply_event(
            session,
            owner_user_id=owner_user_id,
            conv=conv,
            trigger_message_id=trigger_message_id,
            cfg=cfg,
        )
        if not event:
            await session.commit()
            return

        event_id = event.id
        mode = cfg.mode
        delay = random.uniform(cfg.delay_min_sec, cfg.delay_max_sec)
        draft_text = event.draft_text
        target_lang = event.target_lang
        await session.commit()

    if mode == CompanionBotMode.draft:
        await hub.broadcast_user(
            owner_user_id,
            {
                "type": "companion_draft",
                "conversation_id": conv_id,
                "event": {
                    "id": event_id,
                    "conversation_id": conv_id,
                    "trigger_message_id": trigger_message_id,
                    "draft_text": draft_text,
                    "target_lang": target_lang,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            },
        )
        return

    if delay > 0:
        await asyncio.sleep(delay)

    async with SessionLocal() as session:
        conv = await session.get(Conversation, conv_id)
        if not conv:
            return
        if await _is_stale_trigger(session, conv_id, trigger_message_id):
            ev = await session.get(BotResponseEvent, event_id)
            if ev and ev.status == BotResponseEventStatus.draft:
                ev.status = BotResponseEventStatus.rejected
                await session.commit()
            return

        ev = await session.get(BotResponseEvent, event_id)
        if not ev or ev.status != BotResponseEventStatus.draft:
            return

        try:
            row = await approve_and_send_companion_draft(
                session,
                owner_user_id=owner_user_id,
                conv=conv,
                event=ev,
            )
            await session.commit()
            await session.refresh(row, attribute_names=["attachments"])
            await broadcast_companion_message(
                owner_id=owner_user_id, conv_id=conv_id, row=row
            )
        except Exception as e:
            log.warning("companion send failed conv=%s event=%s: %s", conv_id, event_id, e)
            ev.status = BotResponseEventStatus.failed
            await session.commit()
