from __future__ import annotations

from io import BytesIO

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.config import settings
from app.db.models import User
from app.db.session import get_session
from app.schemas import (
    PartnerLinkCreateIn,
    PartnerLinkOut,
    PartnerMeOut,
    PartnerPayoutRequestCreateIn,
    PartnerPayoutSettingsIn,
    PartnerReferralRowOut,
    PayoutAssetOptionOut,
)
from app.services.creator_donation_payout import PAYOUT_ASSET_OPTIONS
from app.services.partner import (
    create_partner_link,
    find_partner_by_slug,
    partner_analytics,
    partner_link_url,
    partner_login_redirect_url,
    partner_public_base_link,
    partner_referrals_list,
    record_partner_link_click,
    ensure_partner_slug,
)
from app.services.partner_payout import (
    create_partner_payout_request,
    get_partner_payout_settings,
    list_partner_payout_requests,
    partner_payout_balance,
    payout_settings_to_dict,
    upsert_partner_payout_settings,
)
from app.services.workspace import is_workspace_owner

router = APIRouter(prefix="/partner", tags=["partner"])
redirect_router = APIRouter(tags=["partner-redirect"])


def _require_partner(user: User) -> None:
    if not is_workspace_owner(user):
        raise HTTPException(status_code=403, detail="Доступно владельцу аккаунта")
    if not getattr(user, "is_partner", False):
        raise HTTPException(status_code=403, detail="Партнёрский кабинет недоступен")


@redirect_router.get("/r/{slug}")
async def partner_redirect(
    slug: str,
    src: str | None = Query(default=None),
    to: str = Query(default="home"),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    partner = await find_partner_by_slug(session, slug)
    if partner is None:
        base = settings.public_app_url.rstrip("/")
        return RedirectResponse(url=f"{base}/login", status_code=302)
    await record_partner_link_click(session, partner=partner, source_tag=src)
    await session.commit()
    url = partner_login_redirect_url(partner, source_tag=src, dest=to)
    return RedirectResponse(url=url, status_code=302)


@router.get("/me", response_model=PartnerMeOut)
async def partner_me(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> PartnerMeOut:
    _require_partner(user)
    slug = await ensure_partner_slug(session, user)
    await session.commit()
    analytics = await partner_analytics(session, user.id)
    balance = await partner_payout_balance(session, user_id=user.id)
    ps = payout_settings_to_dict(await get_partner_payout_settings(session, user_id=user.id))
    return PartnerMeOut(
        is_partner=True,
        partner_slug=slug,
        base_link=partner_public_base_link(slug),
        commission_percent=int(settings.partner_commission_percent),
        discount_percent=int(settings.partner_referred_first_payment_discount_percent),
        payout_hold_days=int(settings.partner_payout_hold_days),
        payout_min_kopecks=int(settings.partner_payout_min_rub) * 100,
        analytics=analytics,
        payout_balance=balance,
        payout_settings=ps,
    )


@router.get("/referrals", response_model=list[PartnerReferralRowOut])
async def partner_referrals(
    src: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[PartnerReferralRowOut]:
    _require_partner(user)
    rows = await partner_referrals_list(session, partner_id=user.id, source_tag=src)
    return [PartnerReferralRowOut.model_validate(r) for r in rows]


@router.post("/links", response_model=PartnerLinkOut)
async def partner_create_link(
    body: PartnerLinkCreateIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> PartnerLinkOut:
    _require_partner(user)
    slug = await ensure_partner_slug(session, user)
    try:
        link = await create_partner_link(
            session,
            partner_id=user.id,
            tag=body.tag,
            note=body.note,
            dest=body.dest,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    await session.commit()
    return PartnerLinkOut(
        id=link.id,
        tag=link.tag,
        note=link.note,
        dest=link.dest,
        url=partner_link_url(slug, tag=link.tag, dest=link.dest),
        clicks=0,
        registrations=0,
        paying_users=0,
        earned_kopecks=0,
    )


@router.get("/payout-assets", response_model=list[PayoutAssetOptionOut])
async def partner_payout_assets() -> list[PayoutAssetOptionOut]:
    return [PayoutAssetOptionOut.model_validate(a) for a in PAYOUT_ASSET_OPTIONS]


@router.put("/payout-settings")
async def partner_payout_settings_put(
    body: PartnerPayoutSettingsIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    _require_partner(user)
    data = await upsert_partner_payout_settings(
        session,
        user_id=user.id,
        wallet_address=body.wallet_address,
        payout_asset=body.payout_asset,
    )
    await session.commit()
    return data


@router.post("/payout-requests")
async def partner_payout_request_create(
    body: PartnerPayoutRequestCreateIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    _require_partner(user)
    row = await create_partner_payout_request(session, user_id=user.id, note=body.note)
    await session.commit()
    return row


@router.get("/payout-requests")
async def partner_payout_requests_list(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[dict]:
    _require_partner(user)
    return await list_partner_payout_requests(session, user_id=user.id)


@router.get("/qr")
async def partner_qr_code(
    url: str = Query(min_length=8, max_length=2048),
    user: User = Depends(get_current_user),
) -> Response:
    _require_partner(user)
    target = url.strip()
    if not target.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="invalid url")
    img = qrcode.make(target, box_size=4, border=2)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")
