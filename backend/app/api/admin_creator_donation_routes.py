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
    AdminCreatorDonationLinkOut,
    AdminCreatorDonationRejectIn,
    AdminCreatorDonationWebhookInboxOut,
)
from app.services.creator_donation_cover import resolve_creator_donation_cover
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
