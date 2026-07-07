"""Ingest webhook-событий Tribute → tribute_earning_events."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TributeConnection, TributeEarningEvent

log = logging.getLogger(__name__)

_REVENUE_EVENTS = frozenset(
    {
        "newdonation",
        "recurrentdonation",
        "newsubscription",
        "renewedsubscription",
        "newdigitalproduct",
        "physicalordercreated",
    }
)
_REFUND_EVENTS = frozenset(
    {
        "cancelleddonation",
        "digitalproductrefund",
        "cancelledsubscription",
        "physicalordercanceled",
        "physicalorderrefunded",
    }
)

_AMOUNT_KEYS = (
    "amount",
    "total",
    "price",
    "sum",
    "value",
    "donated_amount",
    "donatedAmount",
    "payment_amount",
    "paymentAmount",
    "amount_minor",
    "amountMinor",
    "total_amount",
    "totalAmount",
    "net_amount",
    "netAmount",
    "gross_amount",
    "grossAmount",
)

_NESTED_AMOUNT_KEYS = (
    "donation",
    "payment",
    "transaction",
    "product",
    "purchase",
    "order",
    "goal",
    "contribution",
    "data",
)

_CURRENCY_KEYS = ("currency", "Currency", "currency_code", "currencyCode")


def _norm_event_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _parse_dt(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if not raw:
        return datetime.now(timezone.utc)
    s = str(raw).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _to_minor(value: Any, currency: Any = None, *, major_units: bool = False) -> int:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return 0
    if num <= 0:
        return 0
    if major_units:
        return int(round(num * 100))
    # Tribute API: целые значения — minor units (копейки/центы).
    if isinstance(value, int):
        return int(value)
    s = str(value).strip()
    if isinstance(value, float) and num == int(num):
        return int(num)
    if "." in s and not s.endswith(".0"):
        return int(round(num * 100))
    return int(round(num))


def _currency_from_payload(payload: dict[str, Any]) -> str | None:
    for key in _CURRENCY_KEYS:
        raw = payload.get(key)
        if raw is not None and str(raw).strip():
            return str(raw).strip().upper()[:8]
    for nested_key in _NESTED_AMOUNT_KEYS:
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            cur = _currency_from_payload(nested)
            if cur:
                return cur
    return None


def _amount_minor_from_payload(payload: dict[str, Any], *, event_name: str) -> int:
    if not isinstance(payload, dict):
        return 0

    currency = _currency_from_payload(payload)

    for key in _AMOUNT_KEYS:
        if key in payload and payload[key] is not None:
            minor = _to_minor(payload[key], payload.get("currency") or currency)
            if minor:
                return minor

    for nested_key in _NESTED_AMOUNT_KEYS:
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            minor = _amount_minor_from_payload(nested, event_name=event_name)
            if minor:
                return minor

    items = payload.get("items")
    if isinstance(items, list) and items:
        total = 0.0
        item_currency = currency
        for item in items:
            if not isinstance(item, dict):
                continue
            price = float(item.get("price") or item.get("amount") or 0)
            qty = int(item.get("quantity") or 1)
            total += price * qty
            if not item_currency:
                item_currency = _currency_from_payload(item)
        delivery = float(payload.get("deliveryCost") or payload.get("delivery_cost") or 0)
        return _to_minor(total + delivery, item_currency or currency, major_units=True)

    return 0


def _event_kind(norm: str, payload: dict[str, Any]) -> str | None:
    if norm in _REVENUE_EVENTS:
        return "revenue"
    if norm in _REFUND_EVENTS:
        return "refund"
    # Цели и некоторые донаты могут приходить под новым именем — если есть сумма и «donat» в имени.
    if "donat" in norm and _amount_minor_from_payload(payload, event_name=norm):
        return "revenue"
    return None


def _external_event_id(conn_id: int, body: dict[str, Any]) -> str:
    name = str(body.get("name") or "")
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
    for key in (
        "id",
        "donation_id",
        "donation_request_id",
        "donationRequestId",
        "subscription_id",
        "order_id",
        "purchase_id",
        "product_id",
        "payment_id",
        "transaction_id",
        "transactionId",
    ):
        if payload.get(key) is not None:
            return f"{conn_id}:{name}:{payload[key]}"
    sent = body.get("sent_at") or body.get("created_at") or ""
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:24]
    return f"{conn_id}:{name}:{sent}:{digest}"


async def ingest_tribute_webhook(
    session: AsyncSession,
    *,
    conn: TributeConnection,
    body: dict[str, Any],
) -> dict[str, Any]:
    name_raw = str(body.get("name") or "").strip()
    if not name_raw:
        return {"ok": True, "skipped": "no_event_name"}

    norm = _norm_event_name(name_raw)
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
    kind = _event_kind(norm, payload)
    if kind is None:
        log.info(
            "tribute webhook skipped unknown event=%s conn=%s keys=%s",
            name_raw,
            conn.id,
            sorted(payload.keys()) if isinstance(payload, dict) else [],
        )
        return {"ok": True, "skipped": norm or name_raw}

    amount_minor = _amount_minor_from_payload(payload, event_name=norm)
    if amount_minor == 0 and kind == "refund":
        amount_minor = abs(_amount_minor_from_payload(payload, event_name=norm))

    if amount_minor == 0:
        log.warning(
            "tribute webhook skipped zero_amount event=%s conn=%s keys=%s payload=%s",
            name_raw,
            conn.id,
            sorted(payload.keys()) if isinstance(payload, dict) else [],
            json.dumps(payload, ensure_ascii=False)[:500],
        )
        return {"ok": True, "skipped": "zero_amount", "event": name_raw}

    if kind == "refund":
        amount_minor = -abs(amount_minor)

    currency = _currency_from_payload(payload) or "USD"
    occurred_at = _parse_dt(body.get("created_at") or body.get("sent_at"))
    external_id = _external_event_id(conn.id, body)

    existing = await session.scalar(
        select(TributeEarningEvent.id).where(
            TributeEarningEvent.external_event_id == external_id
        )
    )
    if existing:
        return {"ok": True, "duplicate": external_id}

    row = TributeEarningEvent(
        user_id=conn.user_id,
        tribute_connection_id=conn.id,
        studio_model_id=conn.studio_model_id,
        external_event_id=external_id,
        event_name=name_raw,
        amount_minor=amount_minor,
        currency=currency,
        occurred_at=occurred_at,
        raw_meta=json.dumps(body, ensure_ascii=False)[:8000],
    )
    session.add(row)
    await session.commit()
    log.info(
        "tribute event stored conn=%s event=%s amount_minor=%s %s",
        conn.id,
        name_raw,
        amount_minor,
        currency,
    )
    return {"ok": True, "stored": external_id, "amount_minor": amount_minor}
