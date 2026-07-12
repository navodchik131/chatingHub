"""CRUD и валидация platform-донатов креаторов."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CreatorDonationEvent,
    CreatorDonationLink,
    CreatorDonationWebhookInbox,
    User,
    UserStudioModel,
)
from app.services.creator_donation_cover import is_stored_cover_path
from app.services.workspace import workspace_owner_id


def cover_preview_url(link_id: int, storage: str | None) -> str | None:
    raw = (storage or "").strip()
    if not raw:
        return None
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if is_stored_cover_path(raw):
        return f"/api/creator-donations/{int(link_id)}/cover"
    return raw

DONATION_CURRENCIES = frozenset({"EUR", "RUB", "USD"})
DONATION_STATUSES = frozenset({"draft", "pending", "active", "rejected", "disabled"})
EDITABLE_STATUSES = frozenset({"draft", "pending", "rejected"})

# Лимиты Tribute для донатов (minor units).
_CURRENCY_LIMITS: dict[str, tuple[int, int]] = {
    "EUR": (100, 200_000),
    "USD": (100, 200_000),
    "RUB": (10_000, 150_000_00),
}


def normalize_donation_currency(raw: str) -> str:
    cur = (raw or "").strip().upper()
    if cur not in DONATION_CURRENCIES:
        raise HTTPException(status_code=400, detail="unsupported currency")
    return cur


def validate_min_amount_minor(currency: str, min_amount_minor: int | None) -> None:
    if min_amount_minor is None:
        return
    lo, hi = _CURRENCY_LIMITS[currency]
    if min_amount_minor < lo or min_amount_minor > hi:
        raise HTTPException(
            status_code=400,
            detail=f"min amount must be between {lo} and {hi} minor units for {currency}",
        )


async def _validate_studio_model(
    session: AsyncSession,
    *,
    owner_id: int,
    studio_model_id: int | None,
) -> None:
    if studio_model_id is None:
        return
    row = await session.scalar(
        select(UserStudioModel.id).where(
            UserStudioModel.id == studio_model_id,
            UserStudioModel.user_id == owner_id,
        )
    )
    if not row:
        raise HTTPException(status_code=400, detail="studio model not found")


def donation_link_to_dict(link: CreatorDonationLink, *, totals: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": link.id,
        "studio_model_id": link.studio_model_id,
        "title": link.title,
        "description": link.description,
        "button_text": link.button_text,
        "cover_image_url": cover_preview_url(link.id, link.cover_image_url),
        "has_cover": bool(link.cover_image_url),
        "currency": link.currency,
        "min_amount_minor": link.min_amount_minor,
        "allow_one_time": bool(link.allow_one_time),
        "allow_recurring": bool(link.allow_recurring),
        "status": link.status,
        "tribute_donation_request_id": link.tribute_donation_request_id,
        "web_link": link.web_link,
        "telegram_link": link.telegram_link,
        "admin_notes": link.admin_notes if link.status == "rejected" else None,
        "created_at": link.created_at,
        "updated_at": link.updated_at,
        "activated_at": link.activated_at,
    }
    if totals:
        out.update(totals)
    return out


async def aggregate_donation_totals(
    session: AsyncSession,
    *,
    link_ids: list[int],
) -> dict[int, dict[str, Any]]:
    if not link_ids:
        return {}
    rows = (
        await session.execute(
            select(
                CreatorDonationEvent.creator_donation_link_id,
                CreatorDonationEvent.currency,
                func.coalesce(func.sum(CreatorDonationEvent.amount_minor), 0),
                func.count(CreatorDonationEvent.id),
            )
            .where(
                CreatorDonationEvent.creator_donation_link_id.in_(link_ids),
                CreatorDonationEvent.amount_minor > 0,
            )
            .group_by(
                CreatorDonationEvent.creator_donation_link_id,
                CreatorDonationEvent.currency,
            )
        )
    ).all()
    out: dict[int, dict[str, Any]] = {}
    for link_id, currency, total_minor, count in rows:
        bucket = out.setdefault(
            int(link_id),
            {"donations_count": 0, "totals_by_currency": {}, "pending_payout_by_currency": {}},
        )
        bucket["donations_count"] += int(count or 0)
        bucket["totals_by_currency"][str(currency)] = int(total_minor or 0)
    pending_rows = (
        await session.execute(
            select(
                CreatorDonationEvent.creator_donation_link_id,
                CreatorDonationEvent.currency,
                func.coalesce(func.sum(CreatorDonationEvent.amount_minor), 0),
            )
            .where(
                CreatorDonationEvent.creator_donation_link_id.in_(link_ids),
                CreatorDonationEvent.amount_minor > 0,
                CreatorDonationEvent.payout_status == "pending",
            )
            .group_by(
                CreatorDonationEvent.creator_donation_link_id,
                CreatorDonationEvent.currency,
            )
        )
    ).all()
    for link_id, currency, total_minor in pending_rows:
        bucket = out.setdefault(
            int(link_id),
            {"donations_count": 0, "totals_by_currency": {}, "pending_payout_by_currency": {}},
        )
        bucket["pending_payout_by_currency"][str(currency)] = int(total_minor or 0)
    return out


async def list_creator_donation_links(
    session: AsyncSession,
    *,
    viewer: User,
) -> list[dict[str, Any]]:
    owner_id = workspace_owner_id(viewer)
    rows = (
        await session.scalars(
            select(CreatorDonationLink)
            .where(CreatorDonationLink.user_id == owner_id)
            .order_by(CreatorDonationLink.id.desc())
        )
    ).all()
    link_ids = [r.id for r in rows]
    totals = await aggregate_donation_totals(session, link_ids=link_ids)
    return [donation_link_to_dict(r, totals=totals.get(r.id)) for r in rows]


async def get_creator_donation_link(
    session: AsyncSession,
    *,
    viewer: User,
    link_id: int,
) -> CreatorDonationLink:
    owner_id = workspace_owner_id(viewer)
    row = await session.scalar(
        select(CreatorDonationLink).where(
            CreatorDonationLink.id == link_id,
            CreatorDonationLink.user_id == owner_id,
        )
    )
    if not row:
        raise HTTPException(status_code=404, detail="donation link not found")
    return row


async def create_creator_donation_link(
    session: AsyncSession,
    *,
    viewer: User,
    data: dict[str, Any],
) -> dict[str, Any]:
    owner_id = workspace_owner_id(viewer)
    currency = normalize_donation_currency(str(data.get("currency") or ""))
    min_amount_minor = data.get("min_amount_minor")
    if min_amount_minor is not None:
        min_amount_minor = int(min_amount_minor)
    validate_min_amount_minor(currency, min_amount_minor)
    studio_model_id = data.get("studio_model_id")
    if studio_model_id is not None:
        studio_model_id = int(studio_model_id)
    await _validate_studio_model(session, owner_id=owner_id, studio_model_id=studio_model_id)

    title = str(data.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title required")
    if len(title) > 128:
        raise HTTPException(status_code=400, detail="title too long")

    submit = bool(data.get("submit"))
    status = "pending" if submit else "draft"

    row = CreatorDonationLink(
        user_id=owner_id,
        studio_model_id=studio_model_id,
        title=title,
        description=(str(data["description"]).strip() if data.get("description") else None),
        button_text=(str(data["button_text"]).strip() if data.get("button_text") else None),
        cover_image_url=None,
        currency=currency,
        min_amount_minor=min_amount_minor,
        allow_one_time=bool(data.get("allow_one_time", True)),
        allow_recurring=bool(data.get("allow_recurring", True)),
        status=status,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return donation_link_to_dict(row, totals={"donations_count": 0, "totals_by_currency": {}, "pending_payout_by_currency": {}})


async def update_creator_donation_link(
    session: AsyncSession,
    *,
    viewer: User,
    link_id: int,
    data: dict[str, Any],
) -> dict[str, Any]:
    row = await get_creator_donation_link(session, viewer=viewer, link_id=link_id)
    if row.status not in EDITABLE_STATUSES:
        raise HTTPException(status_code=400, detail="donation link cannot be edited in current status")

    owner_id = workspace_owner_id(viewer)
    if "cover_image_url" in data:
        val = data["cover_image_url"]
        if val is None or str(val).strip() == "":
            pass  # cover managed via upload endpoint
        elif str(val).strip().startswith("http"):
            row.cover_image_url = str(val).strip()

    if "currency" in data:
        row.currency = normalize_donation_currency(str(data["currency"]))
    if "min_amount_minor" in data:
        val = data["min_amount_minor"]
        row.min_amount_minor = int(val) if val is not None else None
    validate_min_amount_minor(row.currency, row.min_amount_minor)

    if "studio_model_id" in data:
        studio_model_id = data["studio_model_id"]
        if studio_model_id is not None:
            studio_model_id = int(studio_model_id)
        await _validate_studio_model(session, owner_id=owner_id, studio_model_id=studio_model_id)
        row.studio_model_id = studio_model_id

    for field in ("title", "description", "button_text"):
        if field in data:
            val = data[field]
            if field == "title":
                title = str(val or "").strip()
                if not title:
                    raise HTTPException(status_code=400, detail="title required")
                row.title = title
            elif val is None or str(val).strip() == "":
                setattr(row, field, None)
            else:
                setattr(row, field, str(val).strip())

    if "allow_one_time" in data:
        row.allow_one_time = bool(data["allow_one_time"])
    if "allow_recurring" in data:
        row.allow_recurring = bool(data["allow_recurring"])

    if bool(data.get("submit")):
        row.status = "pending"
    elif row.status == "rejected" and not data.get("submit"):
        row.status = "draft"
        row.admin_notes = None

    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(row)
    totals = await aggregate_donation_totals(session, link_ids=[row.id])
    return donation_link_to_dict(row, totals=totals.get(row.id))


async def delete_creator_donation_link(
    session: AsyncSession,
    *,
    viewer: User,
    link_id: int,
) -> None:
    row = await get_creator_donation_link(session, viewer=viewer, link_id=link_id)
    if row.status == "active":
        raise HTTPException(status_code=400, detail="active donation link cannot be deleted")
    await session.delete(row)
    await session.commit()


async def upload_creator_donation_cover(
    session: AsyncSession,
    *,
    viewer: User,
    link_id: int,
    raw: bytes,
    content_type: str | None,
    filename: str | None,
) -> dict[str, Any]:
    from app.services.creator_donation_cover import (
        delete_creator_donation_cover_file,
        save_creator_donation_cover,
    )

    row = await get_creator_donation_link(session, viewer=viewer, link_id=link_id)
    if row.status not in EDITABLE_STATUSES:
        raise HTTPException(status_code=400, detail="donation link cannot be edited in current status")
    owner_id = workspace_owner_id(viewer)
    delete_creator_donation_cover_file(row.cover_image_url)
    rel = save_creator_donation_cover(
        owner_id=owner_id,
        link_id=row.id,
        raw=raw,
        content_type=content_type,
        filename=filename,
    )
    row.cover_image_url = rel
    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(row)
    totals = await aggregate_donation_totals(session, link_ids=[row.id])
    return donation_link_to_dict(row, totals=totals.get(row.id))


async def list_creator_donation_events(
    session: AsyncSession,
    *,
    viewer: User,
    link_id: int | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    owner_id = workspace_owner_id(viewer)
    stmt = (
        select(CreatorDonationEvent)
        .where(CreatorDonationEvent.user_id == owner_id)
        .order_by(CreatorDonationEvent.occurred_at.desc())
        .limit(max(1, min(limit, 500)))
    )
    if link_id is not None:
        stmt = stmt.where(CreatorDonationEvent.creator_donation_link_id == link_id)
    rows = (await session.scalars(stmt)).all()
    return [
        {
            "id": r.id,
            "creator_donation_link_id": r.creator_donation_link_id,
            "studio_model_id": r.studio_model_id,
            "event_name": r.event_name,
            "amount_minor": r.amount_minor,
            "currency": r.currency,
            "payer_telegram_user_id": r.payer_telegram_user_id,
            "payout_status": r.payout_status,
            "occurred_at": r.occurred_at,
        }
        for r in rows
    ]


async def admin_list_creator_donation_links(
    session: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    stmt = select(CreatorDonationLink).order_by(CreatorDonationLink.updated_at.desc()).limit(
        max(1, min(limit, 500))
    )
    if status:
        if status == "moderation":
            stmt = stmt.where(CreatorDonationLink.status.in_(["pending", "awaiting_id"]))
        else:
            stmt = stmt.where(CreatorDonationLink.status == status)
    rows = (await session.scalars(stmt)).all()
    link_ids = [r.id for r in rows]
    totals = await aggregate_donation_totals(session, link_ids=link_ids)
    return [
        {
            **donation_link_to_dict(r, totals=totals.get(r.id)),
            "user_id": r.user_id,
            "admin_notes_internal": r.admin_notes,
        }
        for r in rows
    ]


async def admin_activate_creator_donation_link(
    session: AsyncSession,
    *,
    link_id: int,
    tribute_donation_request_id: int | None,
    web_link: str,
    telegram_link: str | None = None,
) -> dict[str, Any]:
    row = await session.get(CreatorDonationLink, link_id)
    if not row:
        raise HTTPException(status_code=404, detail="donation link not found")
    if row.status not in {"pending", "draft", "disabled", "awaiting_id"}:
        raise HTTPException(status_code=400, detail="donation link cannot be activated")

    if tribute_donation_request_id is not None:
        existing = await session.scalar(
            select(CreatorDonationLink.id).where(
                CreatorDonationLink.tribute_donation_request_id == tribute_donation_request_id,
                CreatorDonationLink.id != link_id,
            )
        )
        if existing:
            raise HTTPException(status_code=400, detail="tribute donation id already used")

    web_link = web_link.strip()
    if not web_link:
        raise HTTPException(status_code=400, detail="web_link required")

    now = datetime.now(timezone.utc)
    row.web_link = web_link
    row.telegram_link = telegram_link.strip() if telegram_link else None
    row.admin_notes = None
    row.updated_at = now

    if tribute_donation_request_id is not None:
        row.tribute_donation_request_id = int(tribute_donation_request_id)
        row.status = "active"
        row.activated_at = now
    else:
        row.status = "awaiting_id"

    await session.commit()
    await session.refresh(row)
    totals = await aggregate_donation_totals(session, link_ids=[row.id])
    return {
        **donation_link_to_dict(row, totals=totals.get(row.id)),
        "user_id": row.user_id,
        "admin_notes_internal": row.admin_notes,
    }


async def admin_bind_creator_donation_request_id(
    session: AsyncSession,
    *,
    link_id: int,
    tribute_donation_request_id: int,
    inbox_id: int | None = None,
    web_link: str | None = None,
    telegram_link: str | None = None,
) -> dict[str, Any]:
    row = await session.get(CreatorDonationLink, link_id)
    if not row:
        raise HTTPException(status_code=404, detail="donation link not found")
    if row.status not in {"pending", "awaiting_id"}:
        raise HTTPException(status_code=400, detail="donation link cannot be bound")

    if web_link is not None:
        web_link = web_link.strip()
        if web_link:
            row.web_link = web_link
    if telegram_link is not None:
        row.telegram_link = telegram_link.strip() or None

    if not (row.web_link or "").strip():
        raise HTTPException(
            status_code=400,
            detail="web_link required before bind — paste Tribute web link in the request card first",
        )

    existing = await session.scalar(
        select(CreatorDonationLink.id).where(
            CreatorDonationLink.tribute_donation_request_id == tribute_donation_request_id,
            CreatorDonationLink.id != link_id,
        )
    )
    if existing:
        raise HTTPException(status_code=400, detail="tribute donation id already used")

    now = datetime.now(timezone.utc)
    row.tribute_donation_request_id = int(tribute_donation_request_id)
    row.status = "active"
    row.activated_at = row.activated_at or now
    row.updated_at = now

    if inbox_id is not None:
        inbox = await session.get(CreatorDonationWebhookInbox, inbox_id)
        if inbox and inbox.resolved_link_id is None:
            inbox.resolved_link_id = row.id
            inbox.resolved_at = now

    await session.commit()
    await session.refresh(row)
    totals = await aggregate_donation_totals(session, link_ids=[row.id])
    return {
        **donation_link_to_dict(row, totals=totals.get(row.id)),
        "user_id": row.user_id,
        "admin_notes_internal": row.admin_notes,
    }


async def admin_list_creator_donation_webhook_inbox(
    session: AsyncSession,
    *,
    unresolved_only: bool = True,
    limit: int = 50,
) -> list[dict[str, Any]]:
    from app.db.models import CreatorDonationWebhookInbox

    stmt = (
        select(CreatorDonationWebhookInbox)
        .order_by(CreatorDonationWebhookInbox.received_at.desc())
        .limit(max(1, min(limit, 200)))
    )
    if unresolved_only:
        stmt = stmt.where(CreatorDonationWebhookInbox.resolved_link_id.is_(None))
    rows = (await session.scalars(stmt)).all()
    return [
        {
            "id": r.id,
            "donation_request_id": r.donation_request_id,
            "event_name": r.event_name,
            "amount_minor": r.amount_minor,
            "currency": r.currency,
            "payer_telegram_user_id": r.payer_telegram_user_id,
            "received_at": r.received_at,
            "resolved_link_id": r.resolved_link_id,
        }
        for r in rows
    ]


async def admin_reject_creator_donation_link(
    session: AsyncSession,
    *,
    link_id: int,
    admin_notes: str | None,
) -> dict[str, Any]:
    row = await session.get(CreatorDonationLink, link_id)
    if not row:
        raise HTTPException(status_code=404, detail="donation link not found")
    if row.status not in {"pending", "awaiting_id"}:
        raise HTTPException(status_code=400, detail="only pending links can be rejected")
    row.status = "rejected"
    row.admin_notes = (admin_notes or "").strip() or None
    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(row)
    totals = await aggregate_donation_totals(session, link_ids=[row.id])
    return {
        **donation_link_to_dict(row, totals=totals.get(row.id)),
        "user_id": row.user_id,
        "admin_notes_internal": row.admin_notes,
    }
