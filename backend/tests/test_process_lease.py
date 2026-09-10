import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from app.services.process_lease import try_acquire_process_lease


def test_process_lease_renew_same_process() -> None:
    async def _run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with Session() as session:
            ok1 = await try_acquire_process_lease(session, "test_lease", ttl_seconds=60)
            assert ok1 is True
        async with Session() as session:
            ok2 = await try_acquire_process_lease(session, "test_lease", ttl_seconds=60)
            assert ok2 is True

        await engine.dispose()

    asyncio.run(_run())
