from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.auth.jwt_utils import create_access_token
from app.auth.passwords import hash_password, verify_password
from app.config import settings
from app.db.models import CreditAccount, Subscription, SubscriptionStatus, User
from app.db.session import get_session
from app.schemas import LoginIn, RegisterIn, TokenOut, UserMeOut
from app.services.admin_access import user_is_platform_admin
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
    session.add(Subscription(user_id=user.id, status=SubscriptionStatus.none))
    session.add(
        CreditAccount(user_id=user.id, balance=max(0, settings.signup_bonus_credits))
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


@router.get("/me", response_model=UserMeOut)
async def me(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserMeOut:
    billing = await resolve_billing_user(session, user)
    sub = billing.subscription
    cr = billing.credit_account
    oid = workspace_owner_id(user)
    owner_row = await session.get(User, oid)
    owner_email = owner_row.email if owner_row else user.email
    return UserMeOut(
        id=user.id,
        email=user.email,
        subscription_status=sub.status.value if sub else SubscriptionStatus.none.value,
        credits_balance=cr.balance if cr else 0,
        is_workspace_owner=user.parent_user_id is None,
        is_platform_admin=user_is_platform_admin(user),
        workspace_owner_id=oid,
        member_login=user.member_login,
        permissions_mask=user.permissions_mask,
        owner_email=owner_email,
    )
