from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.auth_session import user_from_access_token
from app.auth.cookie_auth import read_auth_cookie
from app.db.models import User
from app.db.session import get_session

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    raw_token: str | None = None
    if creds is not None and creds.scheme.lower() == "bearer":
        raw_token = creds.credentials
    if not raw_token:
        raw_token = read_auth_cookie(request)
    if not raw_token:
        raise HTTPException(status_code=401, detail="not authenticated")
    user = await user_from_access_token(session, raw_token)
    stmt = (
        select(User)
        .where(User.id == user.id)
        .options(
            selectinload(User.subscription),
            selectinload(User.credit_account),
        )
    )
    r = await session.execute(stmt)
    loaded = r.scalar_one_or_none()
    if loaded is None:
        raise HTTPException(status_code=401, detail="user not found")
    return loaded


async def get_platform_admin(
    user: User = Depends(get_current_user),
) -> User:
    from app.services.admin_access import user_is_platform_admin

    if not user_is_platform_admin(user):
        raise HTTPException(status_code=403, detail="admin only")
    return user
