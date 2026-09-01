"""Автоотправка paid-медиа после webhook доната Tribute."""

from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    BotResponseEvent,
    BotResponseEventStatus,
    CompanionBotMode,
    Conversation,
    CreatorDonationEvent,
    CreatorDonationLink,
    Platform,
    Subscription,
)
from app.db.repo import list_messages
from app.db.session import SessionLocal
from app.services.companion_bot.config import get_companion_config_for_conversation
from app.services.companion_bot.media_delivery import deliver_companion_media_plan
from app.services.companion_bot.media_planner import MediaPlan, parse_media_plan_from_snapshot
from app.services.companion_bot.prompt import last_fan_message_text, resolve_target_lang
from app.services.companion_bot.send import broadcast_companion_message, send_companion_outbound
from app.services.companion_media.library import get_sent_asset_ids
from app.services.companion_media.search import pick_companion_media
from app.services.plan_entitlements import companion_allowed_for_subscription

log = logging.getLogger(__name__)

_PENDING_OFFER_MAX_AGE_DAYS = 14


def donation_amount_usd_cents(event: CreatorDonationEvent) -> int:
    """Сумма доната в USD-центах (другие валюты пока не конвертируем)."""
    cur = (event.currency or "").upper()
    if cur != "USD":
        return 0
    return max(0, int(event.amount_minor or 0))


def build_unlock_thank_you_text(*, lang: str | None) -> str:
    """Короткая благодарность перед отправкой unlocked контента."""
    code = (lang or "en").strip().lower()[:2]
    if code == "ru":
        return random.choice(
            [
                "спасибо 😏 держи",
                "мм получила 🙈 вот",
                "от души 💋",
            ]
        )
    return random.choice(
        [
            "thank you babe 😏",
            "got it, here you go",
            "mmm enjoy 😘",
        ]
    )


async def find_pending_paid_offer(
    session: AsyncSession,
    *,
    conversation_id: int,
) -> MediaPlan | None:
    """
    Ищем последний отправленный offer_paid в BotResponseEvent,
    у которого promised asset ещё не доставлен этому фану.
    """
    since = datetime.now(timezone.utc) - timedelta(days=_PENDING_OFFER_MAX_AGE_DAYS)
    events = list(
        (
            await session.scalars(
                select(BotResponseEvent)
                .where(
                    BotResponseEvent.conversation_id == conversation_id,
                    BotResponseEvent.status == BotResponseEventStatus.sent,
                    BotResponseEvent.sent_at >= since,
                )
                .order_by(BotResponseEvent.sent_at.desc())
                .limit(12)
            )
        ).all()
    )
    if not events:
        return None

    sent_ids = await get_sent_asset_ids(session, conversation_id=conversation_id)
    for ev in events:
        snapshot: dict = {}
        if ev.state_snapshot_json:
            try:
                parsed = json.loads(ev.state_snapshot_json)
                if isinstance(parsed, dict):
                    snapshot = parsed
            except json.JSONDecodeError:
                continue
        plan = parse_media_plan_from_snapshot(snapshot)
        if plan.action != "offer_paid" or not plan.asset_ids:
            continue
        pending_ids = [aid for aid in plan.asset_ids if aid not in sent_ids]
        if not pending_ids:
            continue
        assets = [a for a in plan.assets if int(a.get("id") or 0) in pending_ids]
        return MediaPlan(
            action="send_paid_unlocked",
            asset_ids=pending_ids,
            assets=assets,
            search_query=plan.search_query,
            reason="donation_unlock_pending_offer",
            price_usd_cents=plan.price_usd_cents,
            matched_tier="paid",
        )
    return None


async def _build_fallback_paid_plan(
    session: AsyncSession,
    *,
    owner_id: int,
    studio_model_id: int,
    conversation_id: int,
    max_price_usd_cents: int,
    search_query: str = "exclusive paid",
) -> MediaPlan | None:
    """Если нет pending offer — подбираем paid-ассет с ценой ≤ сумме доната."""
    try:
        pick = await pick_companion_media(
            session,
            owner_id=owner_id,
            studio_model_id=studio_model_id,
            query=search_query,
            conversation_id=conversation_id,
            expand_pack=True,
            tier="paid",
        )
    except Exception as e:
        log.warning("donation unlock pick failed conv=%s: %s", conversation_id, e)
        return None

    assets = list(pick.get("assets") or [])
    if not assets:
        return None

    price = int(assets[0].get("price_usd_cents") or 0)
    if price <= 0:
        price = 500
    if max_price_usd_cents < price:
        return None

    asset_ids = [int(a["id"]) for a in assets if a.get("id")]
    return MediaPlan(
        action="send_paid_unlocked",
        asset_ids=asset_ids,
        assets=assets,
        search_query=search_query,
        reason="donation_unlock_fallback_pick",
        price_usd_cents=price,
        matched_tier="paid",
    )


async def find_conversations_for_donation_payer(
    session: AsyncSession,
    *,
    owner_id: int,
    payer_telegram_user_id: int,
    studio_model_id: int | None,
) -> list[Conversation]:
    """Диалоги Telegram, где external_chat_id = telegram user id плательщика."""
    rows = list(
        (
            await session.scalars(
                select(Conversation).where(
                    Conversation.user_id == owner_id,
                    Conversation.platform.in_(
                        [Platform.telegram, Platform.telegram_user]
                    ),
                    Conversation.external_chat_id == str(int(payer_telegram_user_id)),
                )
            )
        ).all()
    )
    if not studio_model_id:
        return rows

    matched: list[Conversation] = []
    for conv in rows:
        cfg = await get_companion_config_for_conversation(
            session, conv, owner_id=owner_id
        )
        if not cfg or cfg.studio_model_id != studio_model_id:
            continue
        if cfg.mode not in (CompanionBotMode.auto, CompanionBotMode.semi_auto):
            continue
        matched.append(conv)
    return matched


async def try_unlock_paid_media_for_conversation(
    session: AsyncSession,
    *,
    owner_id: int,
    conv: Conversation,
    donation_event: CreatorDonationEvent,
    studio_model_id: int,
) -> dict[str, object]:
    """Пробует отправить promised paid контент одному диалогу."""
    amount = donation_amount_usd_cents(donation_event)
    if amount <= 0:
        return {"ok": False, "skipped": "non_usd_or_zero_amount"}

    sub = await session.scalar(select(Subscription).where(Subscription.user_id == owner_id))
    if not companion_allowed_for_subscription(sub):
        return {"ok": False, "skipped": "plan_companion_not_allowed"}

    cfg = await get_companion_config_for_conversation(session, conv, owner_id=owner_id)
    if not cfg or cfg.mode not in (CompanionBotMode.auto, CompanionBotMode.semi_auto):
        return {"ok": False, "skipped": "companion_off"}

    plan = await find_pending_paid_offer(session, conversation_id=conv.id)
    if plan is None:
        plan = await _build_fallback_paid_plan(
            session,
            owner_id=owner_id,
            studio_model_id=studio_model_id,
            conversation_id=conv.id,
            max_price_usd_cents=amount,
        )
    if plan is None or not plan.asset_ids:
        return {"ok": False, "skipped": "no_unlockable_assets"}

    required_price = int(plan.price_usd_cents or 0)
    if required_price <= 0 and plan.assets:
        required_price = int(plan.assets[0].get("price_usd_cents") or 0) or 500
    if amount < required_price:
        return {
            "ok": False,
            "skipped": "insufficient_amount",
            "required_usd_cents": required_price,
            "paid_usd_cents": amount,
        }

    history = await list_messages(session, conv.id, owner_id, limit=20)
    lang = resolve_target_lang(conv, last_fan_text=last_fan_message_text(history))
    thank_text = build_unlock_thank_you_text(lang=lang)

    text_row = await send_companion_outbound(
        session,
        owner_id=owner_id,
        conv=conv,
        text=thank_text,
        reply_to_message_id=None,
        bot_response_event_id=0,
        donation_unlock_event_id=donation_event.id,
    )
    await session.flush()
    await broadcast_companion_message(
        owner_id=owner_id, conv_id=conv.id, row=text_row
    )

    media_rows = await deliver_companion_media_plan(
        session,
        owner_id=owner_id,
        conv=conv,
        plan=plan,
        bot_response_event_id=0,
        reply_to_message_id=None,
        donation_unlock_event_id=donation_event.id,
    )
    for media_row in media_rows:
        await session.refresh(media_row, attribute_names=["attachments"])
        await broadcast_companion_message(
            owner_id=owner_id, conv_id=conv.id, row=media_row
        )

    return {
        "ok": True,
        "conversation_id": conv.id,
        "text_message_id": text_row.id,
        "media_message_ids": [r.id for r in media_rows],
        "asset_ids": plan.asset_ids,
        "donation_event_id": donation_event.id,
    }


async def process_donation_unlock_for_event(
    session: AsyncSession,
    *,
    creator_donation_event_id: int,
) -> dict[str, object]:
    """Обрабатывает один CreatorDonationEvent — ищет диалоги и шлёт unlock."""
    event = await session.get(CreatorDonationEvent, creator_donation_event_id)
    if not event:
        return {"ok": False, "skipped": "event_not_found"}

    if int(event.amount_minor or 0) <= 0:
        return {"ok": False, "skipped": "refund_or_zero"}

    payer_tid = event.payer_telegram_user_id
    if payer_tid is None:
        return {"ok": False, "skipped": "no_payer_telegram_id"}

    link = await session.get(CreatorDonationLink, event.creator_donation_link_id)
    studio_model_id = event.studio_model_id or (link.studio_model_id if link else None)
    if not studio_model_id:
        return {"ok": False, "skipped": "no_studio_model"}

    convs = await find_conversations_for_donation_payer(
        session,
        owner_id=event.user_id,
        payer_telegram_user_id=int(payer_tid),
        studio_model_id=int(studio_model_id),
    )
    if not convs:
        return {"ok": False, "skipped": "no_matching_conversations"}

    results: list[dict[str, object]] = []
    for conv in convs:
        try:
            result = await try_unlock_paid_media_for_conversation(
                session,
                owner_id=event.user_id,
                conv=conv,
                donation_event=event,
                studio_model_id=int(studio_model_id),
            )
            results.append(result)
        except Exception as e:
            log.warning(
                "donation unlock failed conv=%s event=%s: %s",
                conv.id,
                creator_donation_event_id,
                e,
            )
            results.append({"ok": False, "conversation_id": conv.id, "error": str(e)[:200]})

    delivered = [r for r in results if r.get("ok")]
    return {
        "ok": bool(delivered),
        "donation_event_id": creator_donation_event_id,
        "conversations_tried": len(convs),
        "delivered": len(delivered),
        "results": results,
    }


async def run_companion_donation_unlock_job(*, creator_donation_event_id: int) -> None:
    async with SessionLocal() as session:
        try:
            summary = await process_donation_unlock_for_event(
                session,
                creator_donation_event_id=creator_donation_event_id,
            )
            await session.commit()
            if summary.get("delivered"):
                log.info(
                    "companion donation unlock event=%s delivered=%s summary=%s",
                    creator_donation_event_id,
                    summary.get("delivered"),
                    summary,
                )
            else:
                log.info(
                    "companion donation unlock event=%s skipped summary=%s",
                    creator_donation_event_id,
                    summary,
                )
        except Exception:
            log.exception(
                "companion donation unlock job failed event=%s",
                creator_donation_event_id,
            )
            await session.rollback()


def schedule_companion_donation_unlock(*, creator_donation_event_id: int) -> None:
    """Фоновая задача после webhook доната."""
    log.info(
        "companion donation unlock scheduled event=%s",
        creator_donation_event_id,
    )

    async def _run() -> None:
        await run_companion_donation_unlock_job(
            creator_donation_event_id=creator_donation_event_id
        )

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        asyncio.run(_run())
