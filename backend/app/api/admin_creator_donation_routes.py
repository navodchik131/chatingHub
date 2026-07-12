"""Admin API platform-донатов креаторов."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_platform_admin
from app.db.models import User
from app.db.session import get_session
from app.schemas import (
    AdminCreatorDonationActivateIn,
    AdminCreatorDonationLinkOut,
    AdminCreatorDonationRejectIn,
)
from app.services.creator_donations import (
    admin_activate_creator_donation_link,
    admin_list_creator_donation_links,
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
