
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.jwt_utils import create_access_token
from app.auth.passwords import hash_password, verify_password
from app.config import settings
from app.db.models import CreditAccount, Subscription, SubscriptionStatus, User
from app.db.session import get_session
from app.schemas import LoginIn, PlanLimitsOut, PlanUsageOut, RegisterIn, TokenOut, UserMeOut
from app.services.admin_access import user_is_platform_admin
from app.services.billing_plan import BILLING_PLAN_CREDITS, BILLING_PLAN_STANDARD, normalize_billing_plan
from app.services.plan_catalog import normalize_plan_tier, plan_display_name
from app.services.plan_entitlements import chat_allowed_for_subscription, plan_usage_snapshot
from app.services.referral import apply_referral_on_signup, ensure_owner_referral_code
from app.services.starter_plan import ensure_starter_managed_subscription, starter_managed_effective
from app.services.funnel_analytics import record_funnel_event_once
from app.services.studio_workflow_defaults import ensure_default_workflow_workspaces
from app.services.workspace import resolve_billing_user, workspace_owner_id

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
async def register(body: RegisterIn, session: AsyncSession = Depends(get_session)) -> TokenOut:
    stmt = select(User).where(User.email == body.email.lower().strip())
    if (await session.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="email already registered")
    email = body.email.lower().strip()
    user = User(
        email=email,
        hashed_password=hash_password(body.password),
        is_active=True,
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
    session.add(
        CreditAccount(
            user_id=user.id,
            balance=bonus,
            demo_generations_remaining=demo_grant,
        )
    )
    await session.flush()
    await apply_referral_on_signup(
        session, new_owner=user, referral_code=body.referral_code
    )
    await ensure_owner_referral_code(session, user)
    await record_funnel_event_once(session, user=user, event="signup")
    await ensure_default_workflow_workspaces(session, owner_id=user.id)
    await session.commit()
    token = create_access_token(str(user.id))
    return TokenOut(access_token=token)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, session: AsyncSession = Depends(get_session)) -> TokenOut:
    email = body.email.lower().strip()
    ml = (body.member_login or "").strip().lower()
    if ml:
        p_stmt = select(User).where(
            User.email == email,
            User.parent_user_id.is_(None),
        )
        parent = (await session.execute(p_stmt)).scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=401, detail="invalid email or password")
        u_stmt = select(User).where(
            User.parent_user_id == parent.id,
            User.member_login == ml,
        )
        user = (await session.execute(u_stmt)).scalar_one_or_none()
    else:
        u_stmt = select(User).where(
            User.email == email,
            User.parent_user_id.is_(None),
        )
        user = (await session.execute(u_stmt)).scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="account disabled")
    token = create_access_token(str(user.id))
    return TokenOut(access_token=token)


@router.get("/me", response_model=UserMeOut)
async def me(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserMeOut:
    oid = workspace_owner_id(user)
    if await ensure_starter_managed_subscription(session, oid):
        await session.commit()
    billing = await resolve_billing_user(session, user)
    sub = billing.subscription
    cr = billing.credit_account
    owner_row = await session.get(User, oid)
    owner_email = owner_row.email if owner_row else user.email
    billing_plan = normalize_billing_plan(sub.billing_plan if sub else None)
    tier = normalize_plan_tier(sub.plan_tier if sub else None)
    period_end = sub.current_period_end if sub else None
    op_stmt = select(func.count()).select_from(User).where(User.parent_user_id == billing.id)
    operators_count = int((await session.scalar(op_stmt)) or 0)
    usage_raw = await plan_usage_snapshot(session, billing.id, sub)
    lim = usage_raw["limits"]
    plan_usage = PlanUsageOut(
        users=usage_raw["users"],
        models=usage_raw["models"],
        dialogs_this_month=usage_raw["dialogs_this_month"],
        grok_this_month=usage_raw["grok_this_month"],
        limits=PlanLimitsOut(
            max_users=lim["max_users"],
            max_models=lim["max_models"],
            max_dialogs_per_month=lim["max_dialogs_per_month"],
            max_grok_per_month=lim["max_grok_per_month"],
        ),
    )
    return UserMeOut(
        id=user.id,
        email=user.email,
        subscription_status=sub.status.value if sub else SubscriptionStatus.none.value,
        credits_balance=cr.balance if cr else 0,
        billing_plan=billing_plan,
        plan_tier=tier,
        plan_display_name=plan_display_name(billing_plan, tier),
        plan_usage=plan_usage,
        subscription_period_end=period_end,
        operators_count=operators_count,
        is_workspace_owner=user.parent_user_id is None,
        is_platform_admin=user_is_platform_admin(user),
        workspace_owner_id=oid,
        member_login=user.member_login,
        permissions_mask=user.permissions_mask,
        owner_email=owner_email,
        billing_require_active_subscription=settings.billing_require_active_subscription,
        online_payment_available=settings.yookassa_configured,
        signup_bonus_credits=settings.signup_bonus_credits,
        demo_generations_remaining=int(cr.demo_generations_remaining) if cr else 0,
        demo_generations_grant=max(0, int(settings.demo_generations_grant)),
        chat_allowed=chat_allowed_for_subscription(sub),
    )
