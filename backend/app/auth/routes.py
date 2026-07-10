
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.jwt_utils import create_access_token
from app.auth.passwords import hash_password, verify_password
from app.auth.telegram_login import TelegramLoginPayload, verify_telegram_login_payload
from app.config import settings
from app.db.models import Subscription, SubscriptionStatus, User
from app.db.session import get_session
from app.schemas import (
    CompleteOwnerEmailIn,
    LoginIn,
    PlanLimitsOut,
    PlanUsageOut,
    RegisterIn,
    TelegramLoginIn,
    TokenOut,
    UserMeOut,
)
from app.services.admin_access import user_is_platform_admin
from app.services.auth_provision import provision_workspace_owner
from app.services.billing_plan import normalize_billing_plan
from app.services.plan_catalog import normalize_plan_tier, plan_display_name
from app.services.plan_entitlements import chat_allowed_for_subscription, plan_usage_snapshot
from app.services.workflow_entitlements import is_workflow_demo_limited
from app.services.starter_plan import ensure_starter_managed_subscription, starter_managed_effective
from app.services.funnel_analytics import record_funnel_event_once
from app.services.studio_workflow_defaults import (
    provision_demo_workflow_workspaces,
    provision_full_workflow_workspaces,
)
from app.services.telegram_identity import (
    complete_owner_email,
    create_owner_from_telegram,
    find_owner_by_telegram_id,
    is_real_owner_email,
    link_telegram_to_owner,
    owner_email_setup_required,
    owner_telegram_linked,
)
from app.services.workspace import is_workspace_owner, resolve_billing_user, workspace_owner_id

router = APIRouter(prefix="/auth", tags=["auth"])


def _public_email_for(user: User) -> str | None:
    if is_real_owner_email(user.email):
        return user.email
    return None


def _verify_telegram_body(body: TelegramLoginIn) -> TelegramLoginPayload:
    payload = TelegramLoginPayload.model_validate(body.model_dump())
    return verify_telegram_login_payload(
        payload,
        bot_token=settings.telegram_login_bot_token,
        max_age_seconds=settings.telegram_login_max_age_seconds,
    )


@router.post("/register", response_model=TokenOut)
async def register(body: RegisterIn, session: AsyncSession = Depends(get_session)) -> TokenOut:
    stmt = select(User).where(User.email == body.email.lower().strip())
    if (await session.execute(stmt)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="email already registered")
    user = await provision_workspace_owner(
        session,
        email=body.email,
        hashed_password=hash_password(body.password),
        auth_email_verified=True,
        referral_code=body.referral_code,
    )
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


@router.post("/telegram", response_model=TokenOut)
async def telegram_login_or_register(
    body: TelegramLoginIn,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    if not settings.telegram_login_configured:
        raise HTTPException(status_code=503, detail="Telegram Login не настроен на сервере")
    payload = _verify_telegram_body(body)
    existing = await find_owner_by_telegram_id(session, payload.id)
    if existing:
        if not existing.is_active:
            raise HTTPException(status_code=403, detail="account disabled")
        user = existing
        existing.telegram_username = (payload.username or "").strip().lstrip("@")[:64] or None
    else:
        user = await create_owner_from_telegram(
            session,
            telegram_id=payload.id,
            telegram_username=payload.username,
        )
        await record_funnel_event_once(session, user=user, event="signup_telegram")
    await session.commit()
    return TokenOut(access_token=create_access_token(str(user.id)))


@router.post("/telegram/link")
async def telegram_link(
    body: TelegramLoginIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    if not is_workspace_owner(user):
        raise HTTPException(status_code=403, detail="Привязка Telegram только для владельца")
    if not settings.telegram_login_configured:
        raise HTTPException(status_code=503, detail="Telegram Login не настроен на сервере")
    payload = _verify_telegram_body(body)
    await link_telegram_to_owner(
        session,
        user,
        telegram_id=payload.id,
        telegram_username=payload.username,
    )
    await session.commit()
    return {
        "ok": True,
        "telegram_linked": True,
        "telegram_username": user.telegram_username,
    }


@router.delete("/telegram/link")
async def telegram_unlink(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    if not is_workspace_owner(user):
        raise HTTPException(status_code=403, detail="Отвязка Telegram только для владельца")
    if not owner_telegram_linked(user):
        return {"ok": True, "telegram_linked": False}
    if not is_real_owner_email(user.email) or not user.auth_email_verified:
        raise HTTPException(
            status_code=400,
            detail="Сначала укажите рабочий email и пароль — без них отвязать Telegram нельзя",
        )
    user.telegram_id = None
    user.telegram_username = None
    user.telegram_linked_at = None
    await session.commit()
    return {"ok": True, "telegram_linked": False}


@router.post("/email/complete", response_model=TokenOut)
async def complete_email(
    body: CompleteOwnerEmailIn,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> TokenOut:
    if not is_workspace_owner(user):
        raise HTTPException(status_code=403, detail="Только владелец может задать email")
    if not owner_email_setup_required(user):
        raise HTTPException(status_code=400, detail="Email уже настроен")
    await complete_owner_email(
        session,
        user,
        email=body.email,
        password=body.password,
    )
    await session.commit()
    return TokenOut(access_token=create_access_token(str(user.id)))


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
    if not is_workflow_demo_limited(sub, cr):
        if await provision_full_workflow_workspaces(session, owner_id=oid):
            await session.commit()
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
    owner_for_identity = owner_row or user
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
        workflow_demo_limited=is_workflow_demo_limited(sub, cr),
        telegram_linked=owner_telegram_linked(owner_for_identity),
        telegram_username=owner_for_identity.telegram_username,
        email_setup_required=owner_email_setup_required(owner_for_identity)
        if is_workspace_owner(user)
        else False,
        public_email=_public_email_for(owner_for_identity),
        telegram_login_available=settings.telegram_login_configured,
        tribute_billing_available=settings.tribute_billing_configured,
    )
