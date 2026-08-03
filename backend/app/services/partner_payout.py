"""Выплаты партнёрам: баланс, заявки, настройки кошелька."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import PartnerCommission, PartnerPayoutRequest, PartnerPayoutSettings
from app.services.creator_donation_payout import PAYOUT_ASSET_OPTIONS, payout_asset_by_id
from app.services.partner import _kopecks_from_rub, partner_commission_available_at

PAYOUT_REQUEST_STATUSES = frozenset({"requested", "processing", "paid", "rejected"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_commission_available(available_at: datetime, *, now: datetime | None = None) -> bool:
    ref = now or _now()
    dt = available_at if available_at.tzinfo else available_at.replace(tzinfo=timezone.utc)
    return ref >= dt


async def get_partner_payout_settings(
    session: AsyncSession, *, user_id: int
) -> PartnerPayoutSettings | None:
    return await session.get(PartnerPayoutSettings, user_id)


async def upsert_partner_payout_settings(
    session: AsyncSession,
    *,
    user_id: int,
    wallet_address: str,
    payout_asset: str,
) -> dict[str, Any]:
    asset = payout_asset_by_id(payout_asset)
    if asset is None:
        raise HTTPException(status_code=400, detail="invalid payout asset")
    wallet = wallet_address.strip()
    if len(wallet) < 8:
        raise HTTPException(status_code=400, detail="wallet too short")

    row = await session.get(PartnerPayoutSettings, user_id)
    if row is None:
        row = PartnerPayoutSettings(user_id=user_id, wallet_address=wallet)
        session.add(row)
    row.wallet_address = wallet
    row.payout_asset = asset["id"]
    row.payout_currency = asset["payout_currency"]
    row.network = asset.get("network") or ""
    row.updated_at = _now()
    await session.flush()
    return payout_settings_to_dict(row)


def payout_settings_to_dict(row: PartnerPayoutSettings | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "wallet_address": row.wallet_address,
        "payout_currency": row.payout_currency,
        "payout_asset": row.payout_asset,
        "network": row.network,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def partner_payout_balance(session: AsyncSession, *, user_id: int) -> dict[str, int]:
    now = _now()
    rows = (
        await session.execute(
            select(PartnerCommission).where(
                PartnerCommission.partner_user_id == user_id,
                PartnerCommission.status.in_(("hold", "available")),
            )
        )
    ).scalars().all()

    available = 0
    hold = 0
    for c in rows:
        if c.status == "available" or (
            c.status == "hold" and is_commission_available(c.available_at, now=now)
        ):
            if c.status == "hold":
                c.status = "available"
            available += int(c.commission_kopecks or 0)
        elif c.status == "hold":
            hold += int(c.commission_kopecks or 0)

    await session.flush()
    return {"available_kopecks": available, "hold_kopecks": hold}


async def create_partner_payout_request(
    session: AsyncSession,
    *,
    user_id: int,
    note: str | None = None,
) -> dict[str, Any]:
    settings_row = await get_partner_payout_settings(session, user_id=user_id)
    if settings_row is None:
        raise HTTPException(status_code=400, detail="payout settings required")

    open_req = await session.scalar(
        select(PartnerPayoutRequest.id).where(
            PartnerPayoutRequest.user_id == user_id,
            PartnerPayoutRequest.status.in_(("requested", "processing")),
        )
    )
    if open_req:
        raise HTTPException(status_code=400, detail="open payout request exists")

    balance = await partner_payout_balance(session, user_id=user_id)
    amount = int(balance["available_kopecks"])
    min_k = _kopecks_from_rub(settings.partner_payout_min_rub)
    if amount < min_k:
        raise HTTPException(status_code=400, detail="below minimum payout amount")

    req = PartnerPayoutRequest(
        user_id=user_id,
        amount_kopecks=amount,
        wallet_address=settings_row.wallet_address,
        payout_currency=settings_row.payout_currency,
        payout_asset=settings_row.payout_asset,
        network=settings_row.network,
        admin_note=(note or "")[:2000] or None,
    )
    session.add(req)
    await session.flush()

    comms = (
        await session.execute(
            select(PartnerCommission).where(
                PartnerCommission.partner_user_id == user_id,
                PartnerCommission.status == "available",
            )
        )
    ).scalars().all()
    for c in comms:
        c.status = "in_request"
        c.payout_request_id = req.id

    await session.flush()
    return payout_request_to_dict(req)


async def list_partner_payout_requests(
    session: AsyncSession, *, user_id: int | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    stmt = select(PartnerPayoutRequest).order_by(PartnerPayoutRequest.requested_at.desc()).limit(limit)
    if user_id is not None:
        stmt = stmt.where(PartnerPayoutRequest.user_id == user_id)
    rows = (await session.execute(stmt)).scalars().all()
    return [payout_request_to_dict(r) for r in rows]


def payout_request_to_dict(row: PartnerPayoutRequest) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "amount_kopecks": row.amount_kopecks,
        "status": row.status,
        "wallet_address": row.wallet_address,
        "payout_currency": row.payout_currency,
        "payout_asset": row.payout_asset,
        "network": row.network,
        "admin_note": row.admin_note,
        "requested_at": row.requested_at.isoformat() if row.requested_at else None,
        "processed_at": row.processed_at.isoformat() if row.processed_at else None,
    }


async def admin_update_partner_payout_request(
    session: AsyncSession,
    *,
    request_id: int,
    status: str,
    admin_note: str | None,
) -> dict[str, Any]:
    status_norm = (status or "").strip().lower()
    if status_norm not in PAYOUT_REQUEST_STATUSES:
        raise HTTPException(status_code=400, detail="invalid status")
    if status_norm == "requested":
        raise HTTPException(status_code=400, detail="cannot revert to requested")

    row = await session.get(PartnerPayoutRequest, request_id)
    if not row:
        raise HTTPException(status_code=404, detail="payout request not found")

    comms = (
        await session.scalars(
            select(PartnerCommission).where(PartnerCommission.payout_request_id == row.id)
        )
    ).all()

    row.status = status_norm
    if admin_note is not None:
        row.admin_note = admin_note.strip() or row.admin_note

    if status_norm == "processing":
        pass
    elif status_norm == "paid":
        row.processed_at = _now()
        for c in comms:
            c.status = "paid"
    elif status_norm == "rejected":
        row.processed_at = _now()
        for c in comms:
            c.status = "available"
            c.payout_request_id = None

    await session.flush()
    return payout_request_to_dict(row)


async def admin_partner_open_payout_count(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            select(func.count(PartnerPayoutRequest.id)).where(
                PartnerPayoutRequest.status.in_(("requested", "processing"))
            )
        )
        or 0
    )
