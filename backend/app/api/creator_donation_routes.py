"""API platform-донатов креаторов."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.schemas import (
    CreatorDonationEventOut,
    CreatorDonationLinkIn,
    CreatorDonationLinkOut,
    CreatorDonationLinkPatchIn,
    CreatorDonationOverviewOut,
    CreatorPayoutRequestCreateIn,
    CreatorPayoutRequestOut,
    CreatorPayoutSettingsIn,
    CreatorPayoutSettingsOut,
    PayoutAssetOptionOut,
)
from app.services.creator_donation_cover import resolve_creator_donation_cover
from app.services.creator_donation_payout import (
    PAYOUT_ASSET_OPTIONS,
    available_balance_by_currency,
    create_payout_request,
    get_payout_settings,
    list_payout_requests,
    payout_settings_to_dict,
    upsert_payout_settings,
)
from app.services.creator_donations import (
    aggregate_donation_totals,
    create_creator_donation_link,
    creator_donation_overview,
    delete_creator_donation_link,
    donation_link_to_dict as _link_dict,
    get_creator_donation_link,
    list_creator_donation_events,
    list_creator_donation_links,
    update_creator_donation_link,
    upload_creator_donation_cover,
)
from app.services.workspace import is_workspace_owner, workspace_owner_id

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


@router.get("/overview", response_model=CreatorDonationOverviewOut)
async def creator_donations_overview(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CreatorDonationOverviewOut:
    _assert_owner(user)
    data = await creator_donation_overview(session, user_id=workspace_owner_id(user))
    return CreatorDonationOverviewOut.model_validate(data)


@router.get("/payout-assets", response_model=list[PayoutAssetOptionOut])
async def creator_payout_assets(
    user: User = Depends(get_current_user),
) -> list[PayoutAssetOptionOut]:
    _assert_owner(user)
    return [PayoutAssetOptionOut.model_validate(a) for a in PAYOUT_ASSET_OPTIONS]


@router.get("/payout-settings", response_model=CreatorPayoutSettingsOut | None)
async def creator_payout_settings_get(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _assert_owner(user)
    row = await get_payout_settings(session, user_id=workspace_owner_id(user))
    data = payout_settings_to_dict(row)
    return CreatorPayoutSettingsOut.model_validate(data) if data else None


@router.put("/payout-settings", response_model=CreatorPayoutSettingsOut)
async def creator_payout_settings_put(
    body: CreatorPayoutSettingsIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CreatorPayoutSettingsOut:
    _assert_owner(user)
    data = await upsert_payout_settings(
        session,
        user_id=workspace_owner_id(user),
        wallet_address=body.wallet_address,
        payout_asset=body.payout_asset,
    )
    return CreatorPayoutSettingsOut.model_validate(data)


@router.get("/payout-balance")
async def creator_payout_balance(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    _assert_owner(user)
    return await available_balance_by_currency(session, user_id=workspace_owner_id(user))


@router.get("/payout-requests", response_model=list[CreatorPayoutRequestOut])
async def creator_payout_requests_list(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[CreatorPayoutRequestOut]:
    _assert_owner(user)
    rows = await list_payout_requests(session, user_id=workspace_owner_id(user))
    return [CreatorPayoutRequestOut.model_validate(r) for r in rows]


@router.post("/payout-requests", response_model=CreatorPayoutRequestOut)
async def creator_payout_requests_create(
    body: CreatorPayoutRequestCreateIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CreatorPayoutRequestOut:
    _assert_owner(user)
    row = await create_payout_request(
        session,
        user_id=workspace_owner_id(user),
        source_currency=body.source_currency,
    )
    return CreatorPayoutRequestOut.model_validate(row)


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


@router.post("/{link_id}/cover", response_model=CreatorDonationLinkOut)
async def creator_donations_upload_cover(
    link_id: int,
    cover: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CreatorDonationLinkOut:
    _assert_owner(user)
    raw = await cover.read()
    try:
        row = await upload_creator_donation_cover(
            session,
            viewer=user,
            link_id=link_id,
            raw=raw,
            content_type=cover.content_type,
            filename=cover.filename,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return CreatorDonationLinkOut.model_validate(row)


@router.get("/{link_id}/cover")
async def creator_donations_get_cover(
    link_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _assert_owner(user)
    row = await get_creator_donation_link(session, viewer=user, link_id=link_id)
    path = resolve_creator_donation_cover(workspace_owner_id(user), row.cover_image_url)
    if not path:
        raise HTTPException(status_code=404, detail="cover not found")
    return FileResponse(path, media_type=None, filename=path.name)


@router.delete("/{link_id}")
async def creator_donations_delete(
    link_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    _assert_owner(user)
    await delete_creator_donation_link(session, viewer=user, link_id=link_id)
    return {"ok": True}
