"""Admin API platform-донатов креаторов."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_platform_admin
from app.db.models import CreatorDonationLink, User
from app.db.session import get_session
from app.schemas import (
    AdminCreatorDonationActivateIn,
    AdminCreatorDonationBindIn,
    AdminCreatorDonationEventOut,
    AdminCreatorDonationLinkOut,
    AdminCreatorDonationRejectIn,
    AdminCreatorDonationStatsOut,
    AdminCreatorDonationWebhookInboxOut,
    AdminCreatorPayoutRequestOut,
    AdminCreatorPayoutRequestUpdateIn,
)
from app.services.creator_donation_cover import resolve_creator_donation_cover
from app.services.creator_donation_payout import (
    admin_donation_stats,
    admin_list_all_events,
    admin_update_payout_request,
    list_payout_requests,
)
from app.services.creator_donations import (
    admin_activate_creator_donation_link,
    admin_bind_creator_donation_request_id,
    admin_list_creator_donation_links,
    admin_list_creator_donation_webhook_inbox,
    admin_reject_creator_donation_link,
)

router = APIRouter(prefix="/admin/creator-donations", tags=["admin"])


@router.get("", response_model=list[AdminCreatorDonationLinkOut])
async def admin_creator_donations_list(
    status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> list[AdminCreatorDonationLinkOut]:
    rows = await admin_list_creator_donation_links(session, status=status, limit=limit)
    return [AdminCreatorDonationLinkOut.model_validate(r) for r in rows]


@router.get("/webhook-inbox", response_model=list[AdminCreatorDonationWebhookInboxOut])
async def admin_creator_donations_webhook_inbox(
    unresolved_only: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=200),
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> list[AdminCreatorDonationWebhookInboxOut]:
    rows = await admin_list_creator_donation_webhook_inbox(
        session, unresolved_only=unresolved_only, limit=limit
    )
    return [AdminCreatorDonationWebhookInboxOut.model_validate(r) for r in rows]


@router.get("/stats", response_model=AdminCreatorDonationStatsOut)
async def admin_creator_donations_stats(
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminCreatorDonationStatsOut:
    data = await admin_donation_stats(session)
    return AdminCreatorDonationStatsOut.model_validate(data)


@router.get("/events", response_model=list[AdminCreatorDonationEventOut])
async def admin_creator_donations_events(
    user_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=200, ge=1, le=500),
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> list[AdminCreatorDonationEventOut]:
    rows = await admin_list_all_events(session, user_id=user_id, limit=limit)
    return [AdminCreatorDonationEventOut.model_validate(r) for r in rows]


@router.get("/payout-requests", response_model=list[AdminCreatorPayoutRequestOut])
async def admin_creator_payout_requests_list(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> list[AdminCreatorPayoutRequestOut]:
    rows = await list_payout_requests(session, limit=limit)
    if status:
        rows = [r for r in rows if r["status"] == status]
    out: list[AdminCreatorPayoutRequestOut] = []
    for row in rows:
        user = await session.get(User, row["user_id"])
        out.append(
            AdminCreatorPayoutRequestOut.model_validate(
                {**row, "user_email": user.email if user else None}
            )
        )
    return out


@router.patch("/payout-requests/{request_id}", response_model=AdminCreatorPayoutRequestOut)
async def admin_creator_payout_request_update(
    request_id: int,
    body: AdminCreatorPayoutRequestUpdateIn,
    admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminCreatorPayoutRequestOut:
    row = await admin_update_payout_request(
        session,
        request_id=request_id,
        status=body.status,
        admin_notes=body.admin_notes,
        admin_user_id=admin.id,
    )
    user = await session.get(User, row["user_id"])
    return AdminCreatorPayoutRequestOut.model_validate(
        {**row, "user_email": user.email if user else None}
    )


@router.get("/{link_id}/cover")
async def admin_creator_donation_cover(
    link_id: int,
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
):
    row = await session.get(CreatorDonationLink, link_id)
    if not row:
        raise HTTPException(status_code=404, detail="donation link not found")
    path = resolve_creator_donation_cover(row.user_id, row.cover_image_url)
    if not path:
        raise HTTPException(status_code=404, detail="cover not found")
    return FileResponse(path, media_type=None, filename=f"donation-cover-{link_id}{path.suffix}")


@router.post("/{link_id}/activate", response_model=AdminCreatorDonationLinkOut)
async def admin_creator_donations_activate(
    link_id: int,
    body: AdminCreatorDonationActivateIn,
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminCreatorDonationLinkOut:
    row = await admin_activate_creator_donation_link(
        session,
        link_id=link_id,
        tribute_donation_request_id=body.tribute_donation_request_id,
        web_link=body.web_link,
        telegram_link=body.telegram_link,
    )
    return AdminCreatorDonationLinkOut.model_validate(row)


@router.post("/{link_id}/bind-donation-id", response_model=AdminCreatorDonationLinkOut)
async def admin_creator_donations_bind(
    link_id: int,
    body: AdminCreatorDonationBindIn,
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminCreatorDonationLinkOut:
    row = await admin_bind_creator_donation_request_id(
        session,
        link_id=link_id,
        tribute_donation_request_id=body.tribute_donation_request_id,
        inbox_id=body.inbox_id,
        web_link=body.web_link,
        telegram_link=body.telegram_link,
    )
    return AdminCreatorDonationLinkOut.model_validate(row)


@router.post("/{link_id}/reject", response_model=AdminCreatorDonationLinkOut)
async def admin_creator_donations_reject(
    link_id: int,
    body: AdminCreatorDonationRejectIn,
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminCreatorDonationLinkOut:
    row = await admin_reject_creator_donation_link(
        session,
        link_id=link_id,
        admin_notes=body.admin_notes,
    )
    return AdminCreatorDonationLinkOut.model_validate(row)
