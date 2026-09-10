import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.auth_session import bump_auth_token_version, user_from_access_token
from app.auth.jwt_utils import create_access_token, decode_token_claims
from app.db.models import Base, User


def test_logout_bump_invalidates_old_jwt() -> None:
    async def _run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with Session() as session:
            user = User(
                email="t@example.com",
                hashed_password="x",
                is_active=True,
                auth_token_version=0,
            )
            session.add(user)
            await session.flush()
            old_token = create_access_token(user.id, token_version=0)
            await bump_auth_token_version(session, user)
            await session.commit()

        async with Session() as session:
            user = await session.get(User, 1)
            assert user is not None
            with pytest.raises(HTTPException):
                await user_from_access_token(session, old_token)
            new_token = create_access_token(
                user.id, token_version=int(user.auth_token_version)
            )
            loaded = await user_from_access_token(session, new_token)
            assert loaded.id == user.id

        uid, tv = decode_token_claims(new_token)
        assert uid == 1
        assert tv >= 1
        await engine.dispose()

    asyncio.run(_run())
