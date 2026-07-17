"""Webhook platform Tribute → донаты креаторов."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.tribute.handlers import (
    _amount_minor_from_payload,
    _currency_from_payload,
    _external_event_id,
    _norm_event_name,
    _parse_dt,
)
from app.db.models import CreatorDonationEvent, CreatorDonationLink, CreatorDonationWebhookInbox

log = logging.getLogger(__name__)

_CREATOR_DONATION_EVENTS = frozenset({"newdonation", "recurrentdonation"})
_CREATOR_DONATION_REFUNDS = frozenset({"cancelleddonation"})


def _payload(body: dict[str, Any]) -> dict[str, Any]:
    p = body.get("payload")
    return p if isinstance(p, dict) else {}


def _telegram_user_id(payload: dict[str, Any]) -> int | None:
    for key in ("telegram_user_id", "telegramUserId", "user_telegram_id"):
        raw = payload.get(key)
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                continue
    return None


def _donation_request_id(payload: dict[str, Any]) -> int | None:
    for key in (
        "donation_request_id",
        "donationRequestId",
        "donation_id",
        "donationId",
        "request_id",
        "requestId",
    ):
        raw = payload.get(key)
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                continue
    for nested_key in ("donation", "goal", "contribution", "data"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            found = _donation_request_id(nested)
            if found is not None:
                return found
    return None


async def _store_unmapped_donation_webhook(
    session: AsyncSession,
    *,
    body: dict[str, Any],
    donation_request_id: int,
    norm: str,
    payload: dict[str, Any],
) -> None:
    external_id = _external_event_id(0, body)
    external_id = f"creator_donation_inbox:{external_id}"
    existing = await session.scalar(
        select(CreatorDonationWebhookInbox.id).where(
            CreatorDonationWebhookInbox.external_event_id == external_id
        )
    )
    if existing:
        return

    amount_minor = abs(_amount_minor_from_payload(payload, event_name=norm))
    currency = _currency_from_payload(payload) or "USD"
    occurred_at = _parse_dt(body.get("created_at") or body.get("sent_at"))
    session.add(
        CreatorDonationWebhookInbox(
            external_event_id=external_id,
            donation_request_id=donation_request_id,
            event_name=str(body.get("name") or norm),
            amount_minor=amount_minor,
            currency=currency,
            payer_telegram_user_id=_telegram_user_id(payload),
            received_at=occurred_at,
            raw_meta=json.dumps(body, ensure_ascii=False)[:8000],
        )
    )
    await session.commit()
    log.info(
        "creator donation inbox stored donation_request_id=%s amount_minor=%s",
        donation_request_id,
        amount_minor,
    )


async def apply_creator_donation_webhook(
    session: AsyncSession,
    *,
    body: dict[str, Any],
) -> dict[str, Any]:
    name_raw = str(body.get("name") or "").strip()
    if not name_raw:
        return {"ok": True, "skipped": "no_event_name"}

    norm = _norm_event_name(name_raw)
    if norm not in _CREATOR_DONATION_EVENTS and norm not in _CREATOR_DONATION_REFUNDS:
        return {"ok": True, "skipped": "not_creator_donation_event"}

    payload = _payload(body)
    donation_request_id = _donation_request_id(payload)
    amount_minor = abs(_amount_minor_from_payload(payload, event_name=norm))

    link = None
    if donation_request_id is not None:
        link = await session.scalar(
            select(CreatorDonationLink).where(
                CreatorDonationLink.tribute_donation_request_id == donation_request_id,
                CreatorDonationLink.status == "active",
            )
        )

    if link is None:
        await _store_unmapped_donation_webhook(
            session,
            body=body,
            donation_request_id=donation_request_id or 0,
            norm=norm,
            payload=payload,
        )
        if donation_request_id is None:
            log.warning(
                "creator donation webhook: no donation_request_id event=%s payload_keys=%s (saved to inbox)",
                name_raw,
                sorted(payload.keys()),
            )
            return {"ok": True, "skipped": "no_donation_request_id", "inboxed": True}
        return {
            "ok": True,
            "skipped": "unmapped_donation_request",
            "donation_request_id": donation_request_id,
            "inboxed": True,
        }

    if amount_minor == 0:
        log.warning(
            "creator donation webhook: zero_amount event=%s link=%s payload=%s",
            name_raw,
            link.id,
            json.dumps(payload, ensure_ascii=False)[:500],
        )
        return {"ok": True, "skipped": "zero_amount", "event": name_raw, "link_id": link.id}

    if norm in _CREATOR_DONATION_REFUNDS:
        amount_minor = -abs(amount_minor)

    currency = _currency_from_payload(payload) or link.currency or "USD"
    occurred_at = _parse_dt(body.get("created_at") or body.get("sent_at"))
    external_id = _external_event_id(0, body)
    external_id = f"creator_donation:{external_id}"

    existing = await session.scalar(
        select(CreatorDonationEvent.id).where(
            CreatorDonationEvent.external_event_id == external_id
        )
    )
    if existing:
        return {"ok": True, "duplicate": external_id}

    payer_tg = _telegram_user_id(payload)
    row = CreatorDonationEvent(
        creator_donation_link_id=link.id,
        user_id=link.user_id,
        studio_model_id=link.studio_model_id,
        external_event_id=external_id,
        event_name=name_raw,
        amount_minor=amount_minor,
        currency=currency,
        payer_telegram_user_id=payer_tg,
        payout_status="pending",
        occurred_at=occurred_at,
        raw_meta=json.dumps(body, ensure_ascii=False)[:8000],
    )
    session.add(row)
    await session.commit()
    log.info(
        "creator donation stored link=%s user=%s amount_minor=%s payer=%s",
        link.id,
        link.user_id,
        amount_minor,
        payer_tg,
    )
    return {
        "ok": True,
        "stored": external_id,
        "creator_user_id": link.user_id,
        "amount_minor": amount_minor,
        "payer_telegram_user_id": payer_tg,
    }
