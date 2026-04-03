from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.db.models import Base

engine = create_async_engine(
    settings.database_url,
    echo=False,
)
SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


def _migrate_sqlite_last_read(sync_conn) -> None:
    from sqlalchemy import inspect

    insp = inspect(sync_conn)
    if not insp.has_table("conversations"):
        return
    cols = [c["name"] for c in insp.get_columns("conversations")]
    if "last_read_message_id" not in cols:
        sync_conn.execute(
            text("ALTER TABLE conversations ADD COLUMN last_read_message_id INTEGER")
        )


async def init_db() -> None:
    """Создаёт таблицы. Каталог для SQLite создаётся в Settings.sqlite_absolute_path."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.database_url.startswith("sqlite"):
            await conn.run_sync(_migrate_sqlite_last_read)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
