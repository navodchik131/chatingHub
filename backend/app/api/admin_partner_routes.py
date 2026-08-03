"""Admin API партнёрской программы."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_platform_admin
from app.db.models import User
from app.db.session import get_session
from app.schemas import AdminPartnerPayoutRequestOut, AdminPartnerPayoutRequestUpdateIn
from app.services.partner_payout import (
    admin_partner_open_payout_count,
    admin_update_partner_payout_request,
    list_partner_payout_requests,
)

router = APIRouter(prefix="/admin/partner", tags=["admin"])


@router.get("/payout-requests", response_model=list[AdminPartnerPayoutRequestOut])
async def admin_partner_payout_requests_list(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> list[AdminPartnerPayoutRequestOut]:
    rows = await list_partner_payout_requests(session, limit=limit)
    if status:
        rows = [r for r in rows if r["status"] == status]
    out: list[AdminPartnerPayoutRequestOut] = []
    for row in rows:
        user = await session.get(User, row["user_id"])
        out.append(
            AdminPartnerPayoutRequestOut.model_validate(
                {**row, "user_email": user.email if user else None}
            )
        )
    return out


@router.get("/payout-requests/open-count")
async def admin_partner_payout_open_count(
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    count = await admin_partner_open_payout_count(session)
    return {"open_count": count}


@router.patch("/payout-requests/{request_id}", response_model=AdminPartnerPayoutRequestOut)
async def admin_partner_payout_request_update(
    request_id: int,
    body: AdminPartnerPayoutRequestUpdateIn,
    _admin: User = Depends(get_platform_admin),
    session: AsyncSession = Depends(get_session),
) -> AdminPartnerPayoutRequestOut:
    row = await admin_update_partner_payout_request(
        session,
        request_id=request_id,
        status=body.status,
        admin_note=body.admin_notes,
    )
    await session.commit()
    user = await session.get(User, row["user_id"])
    return AdminPartnerPayoutRequestOut.model_validate(
        {**row, "user_email": user.email if user else None}
    )
