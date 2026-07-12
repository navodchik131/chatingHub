"""Выплаты донатов креаторам: баланс, заявки, комиссия платформы."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CreatorDonationEvent,
    CreatorDonationLink,
    CreatorDonationPayoutRequest,
    CreatorPayoutSettings,
    User,
)

PLATFORM_FEE_RATE = Decimal("0.02")

TRIBUTE_PAYOUT_MIN_MINOR: dict[str, int] = {
    "RUB": 300_000,
    "EUR": 10_000,
    "USD": 10_000,
}

PAYOUT_ASSET_OPTIONS: list[dict[str, str]] = [
    {"id": "USDT_TRC20", "label": "USDT (TRC20)", "payout_currency": "USDT", "network": "TRC20"},
    {"id": "USDT_ERC20", "label": "USDT (ERC20)", "payout_currency": "USDT", "network": "ERC20"},
    {"id": "USDT_TON", "label": "USDT (TON)", "payout_currency": "USDT", "network": "TON"},
    {"id": "TON", "label": "TON", "payout_currency": "TON", "network": "TON"},
]

PAYOUT_REQUEST_STATUSES = frozenset({"requested", "processing", "paid", "rejected"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def donation_available_at(occurred_at: datetime) -> datetime:
    dt = occurred_at if occurred_at.tzinfo else occurred_at.replace(tzinfo=timezone.utc)
    y, m, d = dt.year, dt.month, dt.day
    if d <= 15:
        return datetime(y, m, 16, tzinfo=timezone.utc)
    if m == 12:
        return datetime(y + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(y, m + 1, 1, tzinfo=timezone.utc)


def is_donation_available(occurred_at: datetime, *, now: datetime | None = None) -> bool:
    ref = now or _now()
    return ref >= donation_available_at(occurred_at)


def calc_platform_fee(amount_minor: int) -> tuple[int, int]:
    gross = int(amount_minor)
    fee = int((Decimal(gross) * PLATFORM_FEE_RATE).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return fee, gross - fee


def payout_asset_by_id(asset_id: str) -> dict[str, str] | None:
    key = (asset_id or "").strip()
    for item in PAYOUT_ASSET_OPTIONS:
        if item["id"] == key:
            return item
    return None


async def get_payout_settings(session: AsyncSession, *, user_id: int) -> CreatorPayoutSettings | None:
    return await session.get(CreatorPayoutSettings, user_id)


async def upsert_payout_settings(
    session: AsyncSession,
    *,
    user_id: int,
    wallet_address: str,
    payout_asset: str,
) -> dict[str, Any]:
    asset = payout_asset_by_id(payout_asset)
    if not asset:
        raise HTTPException(status_code=400, detail="invalid payout asset")
    wallet = wallet_address.strip()
    if len(wallet) < 8:
        raise HTTPException(status_code=400, detail="wallet address too short")

    row = await session.get(CreatorPayoutSettings, user_id)
    if row is None:
        row = CreatorPayoutSettings(user_id=user_id, wallet_address=wallet)
        session.add(row)
    row.wallet_address = wallet
    row.payout_asset = asset["id"]
    row.payout_currency = asset["payout_currency"]
    row.network = asset["network"]
    row.updated_at = _now()
    await session.commit()
    await session.refresh(row)
    return payout_settings_to_dict(row)


def payout_settings_to_dict(row: CreatorPayoutSettings | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "wallet_address": row.wallet_address,
        "payout_currency": row.payout_currency,
        "network": row.network,
        "payout_asset": row.payout_asset,
        "updated_at": row.updated_at,
    }


async def _eligible_events(
    session: AsyncSession,
    *,
    user_id: int,
    currency: str,
) -> list[CreatorDonationEvent]:
    now = _now()
    rows = (
        await session.scalars(
            select(CreatorDonationEvent)
            .where(
                CreatorDonationEvent.user_id == user_id,
                CreatorDonationEvent.currency == currency.upper(),
                CreatorDonationEvent.amount_minor > 0,
                CreatorDonationEvent.payout_status == "pending",
            )
            .order_by(CreatorDonationEvent.occurred_at.asc())
        )
    ).all()
    return [r for r in rows if is_donation_available(r.occurred_at, now=now)]


async def available_balance_by_currency(
    session: AsyncSession,
    *,
    user_id: int,
) -> dict[str, int]:
    out: dict[str, int] = {}
    for cur in ("RUB", "EUR", "USD"):
        events = await _eligible_events(session, user_id=user_id, currency=cur)
        if events:
            out[cur] = sum(e.amount_minor for e in events)
    return out


async def create_payout_request(
    session: AsyncSession,
    *,
    user_id: int,
    source_currency: str,
) -> dict[str, Any]:
    cur = source_currency.upper()
    min_minor = TRIBUTE_PAYOUT_MIN_MINOR.get(cur)
    if min_minor is None:
        raise HTTPException(status_code=400, detail="unsupported currency")

    settings = await get_payout_settings(session, user_id=user_id)
    if not settings:
        raise HTTPException(status_code=400, detail="payout settings required")

    open_req = await session.scalar(
        select(CreatorDonationPayoutRequest.id).where(
            CreatorDonationPayoutRequest.user_id == user_id,
            CreatorDonationPayoutRequest.status.in_(("requested", "processing")),
        )
    )
    if open_req:
        raise HTTPException(status_code=400, detail="open payout request exists")

    events = await _eligible_events(session, user_id=user_id, currency=cur)
    amount_minor = sum(e.amount_minor for e in events)
    if amount_minor < min_minor:
        raise HTTPException(status_code=400, detail="below minimum payout amount")

    fee_minor, net_minor = calc_platform_fee(amount_minor)
    req = CreatorDonationPayoutRequest(
        user_id=user_id,
        source_currency=cur,
        amount_minor=amount_minor,
        platform_fee_minor=fee_minor,
        net_amount_minor=net_minor,
        wallet_address=settings.wallet_address,
        payout_currency=settings.payout_currency,
        network=settings.network,
        payout_asset=settings.payout_asset,
        status="requested",
        requested_at=_now(),
    )
    session.add(req)
    await session.flush()

    for ev in events:
        ev.payout_status = "in_request"
        ev.payout_request_id = req.id

    await session.commit()
    await session.refresh(req)
    return payout_request_to_dict(req)


async def list_payout_requests(
    session: AsyncSession,
    *,
    user_id: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt = select(CreatorDonationPayoutRequest).order_by(
        CreatorDonationPayoutRequest.requested_at.desc()
    ).limit(max(1, min(limit, 500)))
    if user_id is not None:
        stmt = stmt.where(CreatorDonationPayoutRequest.user_id == user_id)
    rows = (await session.scalars(stmt)).all()
    return [payout_request_to_dict(r) for r in rows]


def payout_request_to_dict(row: CreatorDonationPayoutRequest) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "source_currency": row.source_currency,
        "amount_minor": row.amount_minor,
        "platform_fee_minor": row.platform_fee_minor,
        "net_amount_minor": row.net_amount_minor,
        "wallet_address": row.wallet_address,
        "payout_currency": row.payout_currency,
        "network": row.network,
        "payout_asset": row.payout_asset,
        "status": row.status,
        "admin_notes": row.admin_notes,
        "requested_at": row.requested_at,
        "processed_at": row.processed_at,
        "processed_by_admin_id": row.processed_by_admin_id,
    }


async def admin_update_payout_request(
    session: AsyncSession,
    *,
    request_id: int,
    status: str,
    admin_notes: str | None,
    admin_user_id: int,
) -> dict[str, Any]:
    status_norm = (status or "").strip().lower()
    if status_norm not in PAYOUT_REQUEST_STATUSES:
        raise HTTPException(status_code=400, detail="invalid status")
    if status_norm == "requested":
        raise HTTPException(status_code=400, detail="cannot revert to requested")

    row = await session.get(CreatorDonationPayoutRequest, request_id)
    if not row:
        raise HTTPException(status_code=404, detail="payout request not found")

    events = (
        await session.scalars(
            select(CreatorDonationEvent).where(CreatorDonationEvent.payout_request_id == row.id)
        )
    ).all()

    row.status = status_norm
    row.admin_notes = (admin_notes or "").strip() or row.admin_notes
    row.processed_by_admin_id = admin_user_id
    if status_norm in ("paid", "rejected"):
        row.processed_at = _now()
        for ev in events:
            if status_norm == "paid":
                ev.payout_status = "paid"
            else:
                ev.payout_status = "pending"
                ev.payout_request_id = None
    elif status_norm == "processing":
        for ev in events:
            ev.payout_status = "in_request"

    await session.commit()
    await session.refresh(row)
    return payout_request_to_dict(row)


async def admin_donation_stats(session: AsyncSession) -> dict[str, Any]:
    events = (
        await session.scalars(
            select(CreatorDonationEvent).where(CreatorDonationEvent.amount_minor > 0)
        )
    ).all()

    totals: dict[str, int] = {}
    pending_transfer: dict[str, int] = {}
    platform_fee: dict[str, int] = {}
    by_user: dict[int, dict[str, Any]] = {}

    for ev in events:
        cur = ev.currency.upper()
        totals[cur] = totals.get(cur, 0) + ev.amount_minor
        if ev.payout_status in ("pending", "in_request") and is_donation_available(ev.occurred_at):
            pending_transfer[cur] = pending_transfer.get(cur, 0) + ev.amount_minor
            fee, _ = calc_platform_fee(ev.amount_minor)
            platform_fee[cur] = platform_fee.get(cur, 0) + fee

        bucket = by_user.setdefault(
            ev.user_id,
            {"user_id": ev.user_id, "totals_by_currency": {}, "pending_by_currency": {}},
        )
        bucket["totals_by_currency"][cur] = bucket["totals_by_currency"].get(cur, 0) + ev.amount_minor
        if ev.payout_status in ("pending", "in_request") and is_donation_available(ev.occurred_at):
            bucket["pending_by_currency"][cur] = (
                bucket["pending_by_currency"].get(cur, 0) + ev.amount_minor
            )

    user_ids = list(by_user.keys())
    emails: dict[int, str] = {}
    if user_ids:
        users = (await session.scalars(select(User).where(User.id.in_(user_ids)))).all()
        emails = {u.id: u.email or f"user#{u.id}" for u in users}

    creators = []
    for uid, data in by_user.items():
        net_by_currency = {}
        fee_by_currency = {}
        for cur, amt in data["pending_by_currency"].items():
            fee, net = calc_platform_fee(amt)
            fee_by_currency[cur] = fee
            net_by_currency[cur] = net
        creators.append(
            {
                **data,
                "email": emails.get(uid, f"user#{uid}"),
                "platform_fee_by_currency": fee_by_currency,
                "net_to_transfer_by_currency": net_by_currency,
            }
        )
    creators.sort(key=lambda x: sum(x["totals_by_currency"].values()), reverse=True)

    open_requests = await session.scalar(
        select(func.count(CreatorDonationPayoutRequest.id)).where(
            CreatorDonationPayoutRequest.status.in_(("requested", "processing"))
        )
    )

    active_links = await session.scalar(
        select(func.count(CreatorDonationLink.id)).where(CreatorDonationLink.status == "active")
    )

    return {
        "totals_by_currency": totals,
        "pending_transfer_by_currency": pending_transfer,
        "platform_fee_by_currency": platform_fee,
        "net_to_transfer_by_currency": {
            cur: pending_transfer.get(cur, 0) - platform_fee.get(cur, 0)
            for cur in pending_transfer
        },
        "creators": creators,
        "events_count": len(events),
        "active_links": int(active_links or 0),
        "open_payout_requests": int(open_requests or 0),
        "platform_fee_percent": float(PLATFORM_FEE_RATE * 100),
    }


async def admin_list_all_events(
    session: AsyncSession,
    *,
    user_id: int | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    stmt = (
        select(CreatorDonationEvent, CreatorDonationLink.title, User.email)
        .join(CreatorDonationLink, CreatorDonationLink.id == CreatorDonationEvent.creator_donation_link_id)
        .join(User, User.id == CreatorDonationEvent.user_id)
        .order_by(CreatorDonationEvent.occurred_at.desc())
        .limit(max(1, min(limit, 500)))
    )
    if user_id is not None:
        stmt = stmt.where(CreatorDonationEvent.user_id == user_id)

    rows = (await session.execute(stmt)).all()
    out = []
    for ev, link_title, email in rows:
        fee, net = calc_platform_fee(ev.amount_minor)
        out.append(
            {
                "id": ev.id,
                "user_id": ev.user_id,
                "user_email": email,
                "link_title": link_title,
                "creator_donation_link_id": ev.creator_donation_link_id,
                "amount_minor": ev.amount_minor,
                "currency": ev.currency,
                "platform_fee_minor": fee,
                "net_amount_minor": net,
                "payer_telegram_user_id": ev.payer_telegram_user_id,
                "payout_status": ev.payout_status,
                "payout_request_id": ev.payout_request_id,
                "occurred_at": ev.occurred_at,
            }
        )
    return out
