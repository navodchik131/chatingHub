"""API platform-донатов креаторов."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.schemas import (
    CreatorDonationEventOut,
    CreatorDonationLinkIn,
    CreatorDonationLinkOut,
    CreatorDonationLinkPatchIn,
)
from app.services.creator_donations import (
    create_creator_donation_link,
    delete_creator_donation_link,
    get_creator_donation_link,
    list_creator_donation_events,
    list_creator_donation_links,
    update_creator_donation_link,
)
from app.services.creator_donations import donation_link_to_dict as _link_dict
from app.services.creator_donations import aggregate_donation_totals
from app.services.workspace import is_workspace_owner

router = APIRouter(prefix="/creator-donations", tags=["creator-donations"])


def _assert_owner(user: User) -> None:
    if not is_workspace_owner(user):
        raise HTTPException(status_code=403, detail="owner only")


@router.get("", response_model=list[CreatorDonationLinkOut])
async def creator_donations_list(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CreatorDonationLinkOut]:
    _assert_owner(user)
    rows = await list_creator_donation_links(session, viewer=user)
    return [CreatorDonationLinkOut.model_validate(r) for r in rows]


@router.post("", response_model=CreatorDonationLinkOut)
async def creator_donations_create(
    body: CreatorDonationLinkIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CreatorDonationLinkOut:
    _assert_owner(user)
    row = await create_creator_donation_link(session, viewer=user, data=body.model_dump())
    return CreatorDonationLinkOut.model_validate(row)


@router.get("/events", response_model=list[CreatorDonationEventOut])
async def creator_donations_events(
    link_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CreatorDonationEventOut]:
    _assert_owner(user)
    rows = await list_creator_donation_events(session, viewer=user, link_id=link_id, limit=limit)
    return [CreatorDonationEventOut.model_validate(r) for r in rows]


@router.get("/{link_id}", response_model=CreatorDonationLinkOut)
async def creator_donations_get(
    link_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CreatorDonationLinkOut:
    _assert_owner(user)
    row = await get_creator_donation_link(session, viewer=user, link_id=link_id)
    totals = await aggregate_donation_totals(session, link_ids=[row.id])
    return CreatorDonationLinkOut.model_validate(_link_dict(row, totals=totals.get(row.id)))


@router.patch("/{link_id}", response_model=CreatorDonationLinkOut)
async def creator_donations_patch(
    link_id: int,
    body: CreatorDonationLinkPatchIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CreatorDonationLinkOut:
    _assert_owner(user)
    data = body.model_dump(exclude_unset=True)
    row = await update_creator_donation_link(session, viewer=user, link_id=link_id, data=data)
    return CreatorDonationLinkOut.model_validate(row)


@router.delete("/{link_id}")
async def creator_donations_delete(
    link_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    _assert_owner(user)
    await delete_creator_donation_link(session, viewer=user, link_id=link_id)
    return {"ok": True}
