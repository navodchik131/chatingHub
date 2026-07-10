"""Создание владельца workspace (общая логика register / Telegram)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import CreditAccount, Subscription, SubscriptionStatus, User
from app.services.billing_plan import BILLING_PLAN_CREDITS, BILLING_PLAN_STANDARD
from app.services.funnel_analytics import record_funnel_event_once
from app.services.referral import apply_referral_on_signup, ensure_owner_referral_code
from app.services.starter_plan import starter_managed_effective
from app.services.studio_workflow_defaults import provision_demo_workflow_workspaces


async def provision_workspace_owner(
    session: AsyncSession,
    *,
    email: str,
    hashed_password: str,
    auth_email_verified: bool = True,
    referral_code: str | None = None,
) -> User:
    user = User(
        email=email.lower().strip(),
        hashed_password=hashed_password,
        is_active=True,
        auth_email_verified=auth_email_verified,
    )
    session.add(user)
    await session.flush()

    demo_grant = max(0, int(settings.demo_generations_grant))
    if starter_managed_effective():
        reg_status = SubscriptionStatus.active
        reg_plan = BILLING_PLAN_STANDARD
        demo_grant = 0
    elif settings.yookassa_configured:
        reg_status = SubscriptionStatus.none
        reg_plan = BILLING_PLAN_CREDITS
    else:
        reg_status = SubscriptionStatus.none
        reg_plan = BILLING_PLAN_CREDITS

    session.add(
        Subscription(
            user_id=user.id,
            status=reg_status,
            billing_plan=reg_plan,
            plan_tier="solo",
        )
    )
    bonus = max(0, settings.signup_bonus_credits)
    if reg_plan == BILLING_PLAN_CREDITS:
        bonus = 0
    session.add(
        CreditAccount(
            user_id=user.id,
            balance=bonus,
            demo_generations_remaining=demo_grant,
        )
    )
    await session.flush()
    await apply_referral_on_signup(session, new_owner=user, referral_code=referral_code)
    await ensure_owner_referral_code(session, user)
    await record_funnel_event_once(session, user=user, event="signup")
    await provision_demo_workflow_workspaces(session, owner_id=user.id)
    return user
