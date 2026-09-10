"""Версионирование JWT-сессии — revoke через bump auth_token_version."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_utils import decode_token_claims
from app.db.models import User


async def bump_auth_token_version(session: AsyncSession, user: User) -> int:
    """Инвалидирует все выданные JWT пользователя."""
    user.auth_token_version = int(user.auth_token_version or 0) + 1
    session.add(user)
    await session.flush()
    return int(user.auth_token_version)


async def user_from_access_token(session: AsyncSession, token: str) -> User:
    """Проверяет подпись JWT и совпадение tv с users.auth_token_version."""
    try:
        user_id, token_version = decode_token_claims(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail="invalid token") from e
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="user not found")
    if int(user.auth_token_version or 0) != token_version:
        raise HTTPException(status_code=401, detail="session revoked")
    return user
