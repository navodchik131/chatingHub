"""Оркестрация ответа companion bot."""

from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
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
from app.services.companion_bot.prompt import PROMPT_VERSION, last_fan_message_text, resolve_target_lang
from app.services.companion_bot.send import broadcast_companion_message, send_companion_outbound
from app.services.realtime import hub

log = logging.getLogger(__name__)


async def _broadcast_companion_draft(
    *,
    owner_user_id: int,
    conv_id: int,
    event_id: int,
    trigger_message_id: int,
    draft_text: str,
    target_lang: str | None,
) -> None:
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


async def _notify_companion_draft_fallback(
    *,
    owner_user_id: int,
    conv_id: int,
    event_id: int,
    trigger_message_id: int,
    draft_text: str,
    target_lang: str | None,
) -> None:
    await _broadcast_companion_draft(
        owner_user_id=owner_user_id,
        conv_id=conv_id,
        event_id=event_id,
        trigger_message_id=trigger_message_id,
        draft_text=draft_text,
        target_lang=target_lang,
    )


def _semi_auto_allowed(*, trigger: Message, has_image: bool) -> bool:
    if has_image:
        if not settings.companion_vision_enabled:
            return False
        text = (trigger.text_original or "").strip()
        if not text:
            return False
    text = (trigger.text_original or "").strip()
    if not text and not has_image:
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


async def _fan_replied_after(
    session: AsyncSession, conv_id: int, after_message_id: int
) -> bool:
    newer = await session.scalar(
        select(Message.id)
        .where(
            Message.conversation_id == conv_id,
            Message.direction == MessageDirection.inbound,
            Message.id > after_message_id,
        )
        .limit(1)
    )
    return newer is not None


async def _existing_followup_for_outbound(
    session: AsyncSession, outbound_message_id: int
) -> BotResponseEvent | None:
    return await session.scalar(
        select(BotResponseEvent).where(
            BotResponseEvent.trigger_message_id == outbound_message_id,
            BotResponseEvent.status.in_(
                [BotResponseEventStatus.draft, BotResponseEventStatus.sent]
            ),
        )
    )


async def _should_skip_followup(
    session: AsyncSession,
    conv_id: int,
) -> bool:
    active_min = int(settings.companion_followup_skip_if_fan_active_minutes)
    if active_min > 0:
        since = datetime.now(timezone.utc) - timedelta(minutes=active_min)
        recent_inbound = await session.scalar(
            select(Message.id)
            .where(
                Message.conversation_id == conv_id,
                Message.direction == MessageDirection.inbound,
                Message.created_at >= since,
            )
            .limit(1)
        )
        if recent_inbound:
            return True

    recent = list(
        (
            await session.scalars(
                select(Message)
                .where(Message.conversation_id == conv_id)
                .order_by(Message.id.desc())
                .limit(8)
            )
        ).all()
    )
    outbound_since_fan = 0
    for m in recent:
        if m.direction == MessageDirection.inbound:
            break
        if m.direction == MessageDirection.outbound:
            outbound_since_fan += 1
    return outbound_since_fan >= 2


async def create_companion_followup_event(
    session: AsyncSession,
    *,
    owner_user_id: int,
    conv: Conversation,
    after_outbound_message_id: int,
    cfg: CompanionConnectionConfig,
) -> BotResponseEvent | None:
    if cfg.mode not in (CompanionBotMode.auto, CompanionBotMode.semi_auto):
        return None

    outbound = await session.get(Message, after_outbound_message_id)
    if not outbound or outbound.conversation_id != conv.id:
        return None
    if outbound.direction != MessageDirection.outbound:
        return None

    if await _fan_replied_after(session, conv.id, after_outbound_message_id):
        return None

    if await _existing_followup_for_outbound(session, after_outbound_message_id):
        return None

    if not cfg.studio_model_id:
        return None

    if not await _count_recent_sends(
        session,
        connection_id=cfg.connection_id,
        platform=cfg.platform,
        max_per_hour=cfg.max_replies_per_hour,
    ):
        return None

    history = await list_messages(session, conv.id, owner_user_id, limit=60)
    target_lang = resolve_target_lang(conv, last_fan_text=last_fan_message_text(history))
    try:
        reply, lang, model_name, _, snapshot = await generate_companion_reply(
            session,
            owner_id=owner_user_id,
            conv=conv,
            messages=history,
            studio_model_id=cfg.studio_model_id,
            followup=True,
        )
    except Exception as e:
        log.warning("companion followup generate failed conv=%s: %s", conv.id, e)
        return None

    event = BotResponseEvent(
        conversation_id=conv.id,
        trigger_message_id=after_outbound_message_id,
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


async def run_companion_followup_pipeline(
    *,
    owner_user_id: int,
    conv_id: int,
    after_outbound_message_id: int,
) -> None:
    followup_delay = random.uniform(
        settings.companion_followup_delay_min_sec,
        settings.companion_followup_delay_max_sec,
    )
    await asyncio.sleep(followup_delay)

    async with SessionLocal() as session:
        conv = await session.get(Conversation, conv_id)
        if not conv or conv.user_id != owner_user_id:
            return
        cfg = await get_companion_config_for_conversation(session, conv)
        if not cfg:
            return

        if await _fan_replied_after(session, conv_id, after_outbound_message_id):
            return

        if await _should_skip_followup(session, conv_id):
            log.info("companion followup skipped conv=%s (fan active or outbound streak)", conv_id)
            return

        event = await create_companion_followup_event(
            session,
            owner_user_id=owner_user_id,
            conv=conv,
            after_outbound_message_id=after_outbound_message_id,
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
        await _broadcast_companion_draft(
            owner_user_id=owner_user_id,
            conv_id=conv_id,
            event_id=event_id,
            trigger_message_id=after_outbound_message_id,
            draft_text=draft_text,
            target_lang=target_lang,
        )
        return

    if delay > 0:
        await asyncio.sleep(delay)

    async with SessionLocal() as session:
        conv = await session.get(Conversation, conv_id)
        if not conv:
            return
        cfg = await get_companion_config_for_conversation(session, conv)
        if not cfg or cfg.mode == CompanionBotMode.off:
            ev = await session.get(BotResponseEvent, event_id)
            if ev and ev.status == BotResponseEventStatus.draft:
                ev.status = BotResponseEventStatus.rejected
                await session.commit()
            return
        if cfg.mode == CompanionBotMode.draft:
            ev = await session.get(BotResponseEvent, event_id)
            if ev and ev.status == BotResponseEventStatus.draft:
                await session.commit()
                await _broadcast_companion_draft(
                    owner_user_id=owner_user_id,
                    conv_id=conv_id,
                    event_id=event_id,
                    trigger_message_id=after_outbound_message_id,
                    draft_text=ev.draft_text,
                    target_lang=ev.target_lang,
                )
            return
        if await _fan_replied_after(session, conv_id, after_outbound_message_id):
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
            log.warning(
                "companion followup send failed conv=%s event=%s: %s",
                conv_id,
                event_id,
                e,
            )
            if cfg.mode in (CompanionBotMode.auto, CompanionBotMode.semi_auto):
                await session.commit()
                await _notify_companion_draft_fallback(
                    owner_user_id=owner_user_id,
                    conv_id=conv_id,
                    event_id=event_id,
                    trigger_message_id=after_outbound_message_id,
                    draft_text=ev.draft_text,
                    target_lang=ev.target_lang,
                )
            else:
                ev.status = BotResponseEventStatus.failed
                await session.commit()


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
    if not text_in and not has_image:
        return None
    if not text_in and has_image and not settings.companion_vision_enabled:
        return None

    history = await list_messages(session, conv.id, owner_user_id, limit=60)
    target_lang = resolve_target_lang(
        conv, last_fan_text=text_in or None
    )
    try:
        reply, lang, model_name, _, snapshot = await generate_companion_reply(
            session,
            owner_id=owner_user_id,
            conv=conv,
            messages=history,
            studio_model_id=cfg.studio_model_id,
            trigger_message=trigger,
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
    sender_user_id: int | None = None,
) -> Message:
    if event.status != BotResponseEventStatus.draft:
        raise ValueError("event not in draft status")
    final_text = (text_override or event.draft_text or "").strip()
    if not final_text:
        raise ValueError("empty draft text")
    if text_override and text_override.strip() != (event.draft_text or "").strip():
        event.was_edited = True
        event.draft_text = final_text

    reply_to_id = event.trigger_message_id
    trigger = await session.get(Message, event.trigger_message_id)
    if trigger and trigger.direction == MessageDirection.outbound:
        last_inbound = await session.scalar(
            select(Message.id)
            .where(
                Message.conversation_id == conv.id,
                Message.direction == MessageDirection.inbound,
            )
            .order_by(Message.id.desc())
            .limit(1)
        )
        if last_inbound:
            reply_to_id = last_inbound

    row = await send_companion_outbound(
        session,
        owner_id=owner_user_id,
        conv=conv,
        text=final_text,
        reply_to_message_id=reply_to_id,
        bot_response_event_id=event.id,
        sender_user_id=sender_user_id,
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
        await _broadcast_companion_draft(
            owner_user_id=owner_user_id,
            conv_id=conv_id,
            event_id=event_id,
            trigger_message_id=trigger_message_id,
            draft_text=draft_text,
            target_lang=target_lang,
        )
        return

    if delay > 0:
        await asyncio.sleep(delay)

    async with SessionLocal() as session:
        conv = await session.get(Conversation, conv_id)
        if not conv:
            return
        cfg = await get_companion_config_for_conversation(session, conv)
        if not cfg or cfg.mode == CompanionBotMode.off:
            ev = await session.get(BotResponseEvent, event_id)
            if ev and ev.status == BotResponseEventStatus.draft:
                ev.status = BotResponseEventStatus.rejected
                await session.commit()
            return
        if cfg.mode == CompanionBotMode.draft:
            ev = await session.get(BotResponseEvent, event_id)
            if ev and ev.status == BotResponseEventStatus.draft:
                await session.commit()
                await _broadcast_companion_draft(
                    owner_user_id=owner_user_id,
                    conv_id=conv_id,
                    event_id=event_id,
                    trigger_message_id=trigger_message_id,
                    draft_text=ev.draft_text,
                    target_lang=ev.target_lang,
                )
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
            from app.services.companion_bot.schedule import schedule_companion_followup

            schedule_companion_followup(
                owner_user_id=owner_user_id,
                conv_id=conv_id,
                after_outbound_message_id=row.id,
            )
        except Exception as e:
            log.warning("companion send failed conv=%s event=%s: %s", conv_id, event_id, e)
            if cfg.mode in (CompanionBotMode.auto, CompanionBotMode.semi_auto):
                await session.commit()
                await _notify_companion_draft_fallback(
                    owner_user_id=owner_user_id,
                    conv_id=conv_id,
                    event_id=event_id,
                    trigger_message_id=trigger_message_id,
                    draft_text=ev.draft_text,
                    target_lang=ev.target_lang,
                )
            else:
                ev.status = BotResponseEventStatus.failed
                await session.commit()
