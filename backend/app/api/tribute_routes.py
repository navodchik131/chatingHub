from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db.models import User
from app.db.session import get_session
from app.schemas import TributeEarningsSummaryOut
from app.services.tribute_earnings import aggregate_tribute_earnings
from app.services.workspace import PERM_CHAT, assert_permission

router = APIRouter(prefix="/tribute", tags=["tribute"])


@router.get("/earnings/summary", response_model=TributeEarningsSummaryOut)
async def tribute_earnings_summary(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> TributeEarningsSummaryOut:
    assert_permission(user, PERM_CHAT)
    today = date.today()
    if from_date is None and to_date is None:
        from_date = today.replace(day=1)
        to_date = today
    elif from_date is None:
        from_date = to_date or today
    elif to_date is None:
        to_date = today
    data = await aggregate_tribute_earnings(
        session,
        viewer=user,
        from_date=from_date,
        to_date=to_date,
    )
    return TributeEarningsSummaryOut.model_validate(data)
