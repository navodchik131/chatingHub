from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.jwt_utils import decode_token
from app.db.models import User
from app.db.session import get_session

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="not authenticated")
    try:
        sub = decode_token(creds.credentials)
        user_id = int(sub)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="invalid token") from None
    stmt = (
        select(User)
        .where(User.id == user_id, User.is_active.is_(True))
        .options(
            selectinload(User.subscription),
            selectinload(User.credit_account),
        )
    )
    r = await session.execute(stmt)
    user = r.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    return user


async def get_platform_admin(
    user: User = Depends(get_current_user),
) -> User:
    from app.services.admin_access import user_is_platform_admin

    if not user_is_platform_admin(user):
        raise HTTPException(status_code=403, detail="admin only")
    return user
