"""Планировщик медиа для companion bot: когда, что и за что отправлять."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CompanionMediaSendLog,
    CreatorDonationEvent,
    CreatorDonationLink,
    Conversation,
    Message,
    MessageDirection,
    Platform,
)
from app.services.companion_bot.prompt import (
    ThreadSignals,
    analyze_thread_signals,
    last_fan_message_text,
)
from app.services.companion_media.search import pick_companion_media

log = logging.getLogger(__name__)

MediaAction = Literal[
    "none",
    "send_free",
    "send_teaser",
    "offer_paid",
    "send_paid_unlocked",
    "deflect_no_content",
]

# Лимиты, чтобы бот не спамил медиа как рассылка.
MAX_MEDIA_SENDS_PER_24H = 3
MIN_OUTBOUND_BETWEEN_PROACTIVE = 4
PROACTIVE_MIN_RELATIONSHIP = 42
PROACTIVE_MIN_INBOUND = 2
DONATION_UNLOCK_HOURS = 72

_MEDIA_ASK_HINTS = (
    "photo",
    "pic",
    "picture",
    "selfie",
    "send me",
    "show me",
    "see you",
    "nude",
    "nudes",
    "explicit",
    "фото",
    "фотку",
    "фоточк",
    "селфи",
    "сним",
    "картин",
    "покаж",
    "скинь",
    "скин",
    "видос",
    "видео",
    "video",
)

_EXPLICIT_HINTS = (
    "nude",
    "nudes",
    "explicit",
    "голая",
    "голую",
    "обнаж",
    "сиськ",
    "попк",
    "onlyfans",
    "18+",
)


def detect_fan_media_request(text: str | None) -> bool:
    """Фан явно просит фото/видео."""
    low = (text or "").strip().lower()
    if not low:
        return False
    return any(h in low for h in _MEDIA_ASK_HINTS)


def detect_explicit_request(text: str | None) -> bool:
    low = (text or "").strip().lower()
    if not low:
        return False
    return any(h in low for h in _EXPLICIT_HINTS)


def format_usd_price(price_usd_cents: int) -> str:
    cents = max(0, int(price_usd_cents or 0))
    return f"${cents / 100:.2f}"


def build_media_search_query(
    *,
    messages: list[Message],
    signals: ThreadSignals,
    followup: bool,
    fan_image_description: str | None = None,
) -> str:
    """Семантический запрос для pick_companion_media из контекста диалога."""
    parts: list[str] = []
    fan_text = (signals.last_fan_text or "").strip()
    if fan_text:
        parts.append(fan_text)
    if fan_image_description:
        parts.append(fan_image_description.strip()[:400])

    # Последние 2–3 реплики фана — контекст темы.
    inbound_snips: list[str] = []
    for m in reversed(messages):
        if m.direction != MessageDirection.inbound:
            continue
        t = (m.text_translated or m.text_original or "").strip()
        if t:
            inbound_snips.append(t[:200])
        if len(inbound_snips) >= 3:
            break
    if inbound_snips and inbound_snips[0] != fan_text:
        parts.extend(inbound_snips[1:])

    if followup and not fan_text:
        # Follow-up без нового текста — ищем по последней теме исходящего.
        for m in reversed(messages):
            if m.direction == MessageDirection.outbound:
                t = (m.text_translated or m.text_original or "").strip()
                if t:
                    parts.append(t[:180])
                    break

    query = " ".join(p.strip() for p in parts if p.strip())
    return query[:800]


def choose_media_action(
    *,
    fan_asked: bool,
    explicit_ask: bool,
    relationship_score: int,
    signals: ThreadSignals,
    followup: bool,
    manual_category: str | None,
    recent_media_sends_24h: int,
    outbound_since_last_media: int,
    has_free: bool,
    has_teaser: bool,
    has_paid: bool,
    matched_tier: str | None,
    recent_donation_usd_cents: int,
    asset_price_usd_cents: int,
) -> tuple[MediaAction, str]:
    """
    Чистая логика выбора действия (без БД) — удобно для unit-тестов.
    Возвращает (action, reason).
    """
    cat = (manual_category or "").strip().lower()

    # Не время для медиа: жалоба, фактический допрос, repair.
    if signals.fan_complaint or signals.trust_repair:
        return "none", "fan_complaint_or_trust_repair"
    if signals.direct_factual or signals.factual_pressure:
        if not fan_asked:
            return "none", "factual_qa_no_media"
    if signals.casual_checkin and not fan_asked:
        return "none", "casual_checkin"

    if recent_media_sends_24h >= MAX_MEDIA_SENDS_PER_24H:
        if fan_asked and (has_free or has_teaser or has_paid):
            return "deflect_no_content", "rate_limit_24h"
        return "none", "rate_limit_24h"

    if fan_asked:
        if not matched_tier:
            return "deflect_no_content", "fan_asked_no_match"

        if matched_tier == "free" and has_free:
            return "send_free", "fan_asked_free_match"
        if matched_tier == "teaser" and has_teaser:
            return "send_teaser", "fan_asked_teaser_match"
        if matched_tier == "paid" and has_paid:
            if recent_donation_usd_cents >= asset_price_usd_cents > 0:
                return "send_paid_unlocked", "fan_paid_recently"
            if cat == "bomzh" and not recent_donation_usd_cents:
                return "deflect_no_content", "bomzh_no_paid_offer"
            return "offer_paid", "fan_asked_paid_offer"

        # Совпало что-то, но tier недоступен — мягкий отвод.
        if has_free:
            return "send_free", "fan_asked_fallback_free"
        if has_teaser:
            return "send_teaser", "fan_asked_fallback_teaser"
        return "deflect_no_content", "fan_asked_no_suitable_tier"

    # Проактивный прогрев — только без explicit и не на follow-up.
    if followup or explicit_ask:
        return "none", "no_proactive_followup_or_explicit"
    if cat == "bomzh":
        return "none", "bomzh_no_proactive"
    if relationship_score < PROACTIVE_MIN_RELATIONSHIP:
        return "none", "relationship_too_low"
    if signals.inbound_count < PROACTIVE_MIN_INBOUND:
        return "none", "too_early_in_thread"
    if outbound_since_last_media < MIN_OUTBOUND_BETWEEN_PROACTIVE:
        return "none", "too_soon_after_last_media"

    if has_teaser and relationship_score >= 55:
        return "send_teaser", "proactive_teaser_warm"
    if has_free:
        return "send_free", "proactive_free_warm"
    return "none", "no_proactive_content"


@dataclass
class MediaPlan:
    action: MediaAction = "none"
    asset_ids: list[int] = field(default_factory=list)
    assets: list[dict[str, Any]] = field(default_factory=list)
    search_query: str = ""
    reason: str = ""
    donation_url: str | None = None
    price_usd_cents: int | None = None
    llm_hint: str = ""
    matched_tier: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> MediaPlan:
        if not raw:
            return cls()
        action = raw.get("action") or "none"
        if action not in (
            "none",
            "send_free",
            "send_teaser",
            "offer_paid",
            "send_paid_unlocked",
            "deflect_no_content",
        ):
            action = "none"
        return cls(
            action=action,
            asset_ids=[int(x) for x in (raw.get("asset_ids") or [])],
            assets=list(raw.get("assets") or []),
            search_query=str(raw.get("search_query") or ""),
            reason=str(raw.get("reason") or ""),
            donation_url=raw.get("donation_url"),
            price_usd_cents=raw.get("price_usd_cents"),
            llm_hint=str(raw.get("llm_hint") or ""),
            matched_tier=raw.get("matched_tier"),
        )


def build_media_llm_hint(plan: MediaPlan) -> str:
    """Подсказка LLM: что можно/нельзя обещать в тексте."""
    if plan.action == "none":
        return (
            "MEDIA LIBRARY: do NOT promise to send a photo/video in this reply — "
            "text only. No «sending now» unless you already sent media in a previous message."
        )
    if plan.action in ("send_free", "send_teaser", "send_paid_unlocked"):
        tier_note = {
            "send_free": "a casual free photo",
            "send_teaser": "a teasing preview photo",
            "send_paid_unlocked": "exclusive content they unlocked",
        }.get(plan.action, "media")
        return (
            f"MEDIA LIBRARY: you WILL send {tier_note} right after this text message. "
            "Keep the text short and natural — 1 line teasing or «here» vibe; "
            "do NOT describe pixel details. The file ships automatically after you send."
        )
    if plan.action == "offer_paid":
        price = format_usd_price(plan.price_usd_cents or 0)
        link = (plan.donation_url or "").strip()
        link_part = f" Payment link (include exactly once): {link}" if link else ""
        return (
            f"MEDIA LIBRARY: fan wants more — offer paid exclusive for {price}. "
            f"Flirty, not pushy; no sending the file yet.{link_part} "
            "Do NOT say you're sending the pic now."
        )
    if plan.action == "deflect_no_content":
        return (
            "MEDIA LIBRARY: fan asked for content but nothing suitable to send now. "
            "Playfully deflect like a real person — busy, later, wrong mood, tease without promising "
            "a specific photo. Do NOT say «sending now» or invent content you don't have."
        )
    return ""


async def _count_recent_media_sends(
    session: AsyncSession,
    *,
    conversation_id: int,
    hours: int = 24,
) -> int:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    n = await session.scalar(
        select(func.count())
        .select_from(CompanionMediaSendLog)
        .where(
            CompanionMediaSendLog.conversation_id == conversation_id,
            CompanionMediaSendLog.sent_at >= since,
        )
    )
    return int(n or 0)


async def _outbound_since_last_media(
    session: AsyncSession,
    *,
    conversation_id: int,
) -> int:
    """Сколько исходящих после последней отправки из медиатеки."""
    last_log = await session.scalar(
        select(CompanionMediaSendLog.sent_at)
        .where(CompanionMediaSendLog.conversation_id == conversation_id)
        .order_by(CompanionMediaSendLog.sent_at.desc())
        .limit(1)
    )
    q = select(func.count()).select_from(Message).where(
        Message.conversation_id == conversation_id,
        Message.direction == MessageDirection.outbound,
    )
    if last_log:
        q = q.where(Message.created_at > last_log)
    return int(await session.scalar(q) or 0)


async def _get_active_donation_link(
    session: AsyncSession,
    *,
    owner_id: int,
    studio_model_id: int,
    platform: Platform,
) -> CreatorDonationLink | None:
    row = await session.scalar(
        select(CreatorDonationLink)
        .where(
            CreatorDonationLink.user_id == owner_id,
            CreatorDonationLink.studio_model_id == studio_model_id,
            CreatorDonationLink.status == "active",
        )
        .order_by(CreatorDonationLink.id.desc())
        .limit(1)
    )
    return row


def _donation_url_for_platform(link: CreatorDonationLink | None, platform: Platform) -> str | None:
    if not link:
        return None
    if platform in (Platform.telegram, Platform.telegram_user):
        url = (link.telegram_link or link.web_link or "").strip()
    else:
        url = (link.web_link or link.telegram_link or "").strip()
    return url or None


async def _recent_donation_usd_cents(
    session: AsyncSession,
    *,
    owner_id: int,
    studio_model_id: int,
    conv: Conversation,
) -> int:
    """Сумма недавних донатов фана в USD-центах (для unlock paid контента)."""
    fan_tid: int | None = None
    if conv.platform in (Platform.telegram, Platform.telegram_user):
        try:
            fan_tid = int(conv.external_chat_id)
        except ValueError:
            fan_tid = None
    if fan_tid is None:
        return 0

    since = datetime.now(timezone.utc) - timedelta(hours=DONATION_UNLOCK_HOURS)
    rows = await session.scalars(
        select(CreatorDonationEvent)
        .where(
            CreatorDonationEvent.user_id == owner_id,
            CreatorDonationEvent.studio_model_id == studio_model_id,
            CreatorDonationEvent.payer_telegram_user_id == fan_tid,
            CreatorDonationEvent.occurred_at >= since,
        )
        .order_by(CreatorDonationEvent.occurred_at.desc())
        .limit(5)
    )
    total_minor = 0
    for ev in rows.all():
        cur = (ev.currency or "").upper()
        if cur == "USD":
            total_minor += int(ev.amount_minor or 0)
        # Другие валюты пока не конвертируем — unlock только при явном USD.
    return total_minor


async def _tier_availability(
    session: AsyncSession,
    *,
    owner_id: int,
    studio_model_id: int,
    conversation_id: int,
) -> dict[str, bool]:
    """Есть ли неотправленные ассеты по tier."""
    from app.db.models import CompanionMediaAsset

    sent_ids = await session.scalars(
        select(CompanionMediaSendLog.asset_id).where(
            CompanionMediaSendLog.conversation_id == conversation_id
        )
    )
    sent = {int(x) for x in sent_ids.all()}
    rows = await session.scalars(
        select(CompanionMediaAsset.tier).where(
            CompanionMediaAsset.user_id == owner_id,
            CompanionMediaAsset.studio_model_id == studio_model_id,
            CompanionMediaAsset.status == "active",
        )
    )
    tiers = {str(t).lower() for t in rows.all()}
    # Учитываем только tier, у которых остались неотправленные файлы.
    if sent:
        unsent_rows = await session.scalars(
            select(CompanionMediaAsset.tier).where(
                CompanionMediaAsset.user_id == owner_id,
                CompanionMediaAsset.studio_model_id == studio_model_id,
                CompanionMediaAsset.status == "active",
                CompanionMediaAsset.id.not_in(sent),
            )
        )
        tiers = {str(t).lower() for t in unsent_rows.all()}
    return {
        "free": "free" in tiers,
        "teaser": "teaser" in tiers,
        "paid": "paid" in tiers,
    }


async def plan_companion_media(
    session: AsyncSession,
    *,
    owner_id: int,
    conv: Conversation,
    messages: list[Message],
    studio_model_id: int,
    relationship_score: int,
    followup: bool = False,
    trigger_message: Message | None = None,
    fan_image_description: str | None = None,
    manual_category: str | None = None,
) -> MediaPlan:
    """
    Решает, отправлять ли медиа в этом ходе, и подбирает ассеты из медиатеки.
    Результат кладётся в state_snapshot и подсказку для LLM.
    """
    # Снимок полей conv до pick/embed — после HTTP ORM нельзя трогать без refresh.
    conversation_id = conv.id
    conv_platform = conv.platform
    resolved_manual_category = (manual_category or conv.manual_category or "").strip() or None

    signals = analyze_thread_signals(messages)
    fan_text = last_fan_message_text(messages)
    if trigger_message and trigger_message.direction == MessageDirection.inbound:
        t = (trigger_message.text_translated or trigger_message.text_original or "").strip()
        if t:
            fan_text = t

    fan_asked = detect_fan_media_request(fan_text)
    explicit_ask = detect_explicit_request(fan_text)

    recent_sends = await _count_recent_media_sends(session, conversation_id=conversation_id)
    outbound_gap = await _outbound_since_last_media(session, conversation_id=conversation_id)
    tier_avail = await _tier_availability(
        session,
        owner_id=owner_id,
        studio_model_id=studio_model_id,
        conversation_id=conversation_id,
    )
    donation_link = await _get_active_donation_link(
        session,
        owner_id=owner_id,
        studio_model_id=studio_model_id,
        platform=conv_platform,
    )
    donation_url = _donation_url_for_platform(donation_link, conv_platform)
    recent_donation = await _recent_donation_usd_cents(
        session,
        owner_id=owner_id,
        studio_model_id=studio_model_id,
        conv=conv,
    )

    search_query = build_media_search_query(
        messages=messages,
        signals=signals,
        followup=followup,
        fan_image_description=fan_image_description,
    )

    # Предварительный pick без tier — узнаём лучший match.
    pick_result: dict[str, Any] = {"assets": [], "reason": "skipped"}
    matched_tier: str | None = None
    asset_price = 0
    if search_query and (fan_asked or relationship_score >= PROACTIVE_MIN_RELATIONSHIP):
        try:
            pick_result = await pick_companion_media(
                session,
                owner_id=owner_id,
                studio_model_id=studio_model_id,
                query=search_query,
                conversation_id=conversation_id,
                expand_pack=True,
            )
        except Exception as e:
            log.warning("companion media pick failed conv=%s: %s", conversation_id, e)
            pick_result = {"assets": [], "reason": "pick_error"}

    assets = list(pick_result.get("assets") or [])
    if assets:
        matched_tier = str(assets[0].get("tier") or "teaser").lower()
        asset_price = int(assets[0].get("price_usd_cents") or 0)

    action, reason = choose_media_action(
        fan_asked=fan_asked,
        explicit_ask=explicit_ask,
        relationship_score=relationship_score,
        signals=signals,
        followup=followup,
        manual_category=resolved_manual_category,
        recent_media_sends_24h=recent_sends,
        outbound_since_last_media=outbound_gap,
        has_free=tier_avail["free"],
        has_teaser=tier_avail["teaser"],
        has_paid=tier_avail["paid"],
        matched_tier=matched_tier if assets else None,
        recent_donation_usd_cents=recent_donation,
        asset_price_usd_cents=asset_price,
    )

    plan = MediaPlan(
        action=action,
        search_query=search_query,
        reason=reason,
        donation_url=donation_url,
        matched_tier=matched_tier,
    )

    # Для send_* — переподбираем с фильтром tier и без paid на free/teaser action.
    tier_filter: str | None = None
    if action == "send_free":
        tier_filter = "free"
    elif action == "send_teaser":
        tier_filter = "teaser"
    elif action in ("offer_paid", "send_paid_unlocked"):
        tier_filter = "paid"
    elif action == "send_paid_unlocked":
        tier_filter = "paid"

    if action in ("send_free", "send_teaser", "send_paid_unlocked") and search_query:
        try:
            if tier_filter and tier_filter != matched_tier:
                pick_result = await pick_companion_media(
                    session,
                    owner_id=owner_id,
                    studio_model_id=studio_model_id,
                    query=search_query,
                    conversation_id=conversation_id,
                    expand_pack=True,
                    tier=tier_filter,
                )
                assets = list(pick_result.get("assets") or [])
            if not assets and tier_filter:
                # Fallback: любой доступный в нужном tier.
                pick_result = await pick_companion_media(
                    session,
                    owner_id=owner_id,
                    studio_model_id=studio_model_id,
                    query=tier_filter,
                    conversation_id=conversation_id,
                    expand_pack=True,
                    tier=tier_filter,
                )
                assets = list(pick_result.get("assets") or [])
        except Exception as e:
            log.warning("companion media tier pick failed conv=%s: %s", conversation_id, e)
            assets = []

        if assets:
            plan.assets = assets
            plan.asset_ids = [int(a["id"]) for a in assets if a.get("id")]
            plan.matched_tier = str(assets[0].get("tier") or tier_filter)
            plan.price_usd_cents = int(assets[0].get("price_usd_cents") or 0)
        else:
            plan.action = "deflect_no_content"
            plan.reason = "pick_empty_after_action"
            plan.asset_ids = []
            plan.assets = []

    elif action == "offer_paid":
        try:
            paid_pick = await pick_companion_media(
                session,
                owner_id=owner_id,
                studio_model_id=studio_model_id,
                query=search_query or "exclusive paid",
                conversation_id=conversation_id,
                expand_pack=False,
                tier="paid",
            )
            paid_assets = list(paid_pick.get("assets") or [])
            if paid_assets:
                assets = paid_assets
        except Exception as e:
            log.warning("companion media paid pick failed conv=%s: %s", conversation_id, e)
        if assets:
            plan.assets = assets[:1]
            plan.asset_ids = [int(assets[0]["id"])] if assets[0].get("id") else []
            plan.price_usd_cents = int(assets[0].get("price_usd_cents") or 0) or asset_price
            if not plan.price_usd_cents:
                plan.price_usd_cents = 500  # дефолт $5 если в каталоге не проставлена цена
            plan.matched_tier = "paid"

    plan.llm_hint = build_media_llm_hint(plan)
    return plan


def parse_media_plan_from_snapshot(snapshot: dict[str, Any] | None) -> MediaPlan:
    if not snapshot:
        return MediaPlan()
    raw = snapshot.get("media_plan")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return MediaPlan()
    if isinstance(raw, dict):
        return MediaPlan.from_dict(raw)
    return MediaPlan()
