from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.config import settings
from app.db.models import User
from app.db.session import get_session
from app.schemas import ReferralMeOut
from app.services.referral import (
    ensure_owner_referral_code,
    referral_public_dict,
    referral_stats,
    referrer_reward_summary_text,
)
from app.services.workspace import is_workspace_owner

router = APIRouter(prefix="/referral", tags=["referral"])


@router.get("/me", response_model=ReferralMeOut)
async def referral_me(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ReferralMeOut:
    if not is_workspace_owner(user):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Реферальная программа доступна владельцу аккаунта")
    code = await ensure_owner_referral_code(session, user)
    await session.commit()
    stats = await referral_stats(session, user.id)
    pub = referral_public_dict()
    pct = pub["referrer_payment_percent"]
    unit = pub["credit_unit_price_rub"]
    reward_summary = referrer_reward_summary_text()
    base = settings.public_app_url.rstrip("/")
    link = f"{base}/login?ref={code}"
    return ReferralMeOut(
        referral_code=code,
        referral_link=link,
        invited_count=stats["invited_count"],
        credits_earned=stats["credits_earned"],
        friend_referral_credits=pub["friend_referral_credits"],
        signup_base_credits=pub["signup_base_credits"],
        referrer_payment_percent=pct,
        credit_unit_price_rub=unit,
        referrer_reward_summary=reward_summary,
    )
