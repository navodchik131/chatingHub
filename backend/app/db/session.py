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


def _migrate_conversation_telegram_photo_file_id(sync_conn) -> None:
    from sqlalchemy import inspect

    insp = inspect(sync_conn)
    if not insp.has_table("conversations"):
        return
    cols = [c["name"] for c in insp.get_columns("conversations")]
    if "telegram_photo_file_id" not in cols:
        sync_conn.execute(
            text("ALTER TABLE conversations ADD COLUMN telegram_photo_file_id VARCHAR(200)")
        )


def _migrate_user_workspace_columns(sync_conn) -> None:
    from sqlalchemy import inspect

    insp = inspect(sync_conn)
    if not insp.has_table("users"):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "parent_user_id" not in cols:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN parent_user_id INTEGER"))
    sync_conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_users_parent_user_id ON users(parent_user_id)")
    )
    if "member_login" not in cols:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN member_login VARCHAR(64)"))
    if "permissions_mask" not in cols:
        sync_conn.execute(
            text("ALTER TABLE users ADD COLUMN permissions_mask INTEGER NOT NULL DEFAULT 0")
        )
    # уникальность логина внутри пространства (SQLite)
    sync_conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_workspace_member_login "
            "ON users(parent_user_id, member_login) "
            "WHERE parent_user_id IS NOT NULL AND member_login IS NOT NULL"
        )
    )


def _migrate_conversation_outbound_lang(sync_conn) -> None:
    from sqlalchemy import inspect

    insp = inspect(sync_conn)
    if not insp.has_table("conversations"):
        return
    cols = {c["name"] for c in insp.get_columns("conversations")}
    if "outbound_lang" in cols:
        return
    sync_conn.execute(
        text("ALTER TABLE conversations ADD COLUMN outbound_lang VARCHAR(16)")
    )


def _migrate_telegram_webhook_registered_column(sync_conn) -> None:
    from sqlalchemy import inspect

    insp = inspect(sync_conn)
    if not insp.has_table("telegram_connections"):
        return
    cols = [c["name"] for c in insp.get_columns("telegram_connections")]
    if "webhook_registered" not in cols:
        if sync_conn.dialect.name == "sqlite":
            sync_conn.execute(
                text(
                    "ALTER TABLE telegram_connections ADD COLUMN webhook_registered BOOLEAN NOT NULL DEFAULT 0"
                )
            )
        else:
            sync_conn.execute(
                text(
                    "ALTER TABLE telegram_connections ADD COLUMN webhook_registered BOOLEAN NOT NULL DEFAULT false"
                )
            )


async def init_db() -> None:
    """Создаёт таблицы. Каталог для SQLite создаётся в Settings.sqlite_absolute_path."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if settings.database_url.startswith("sqlite"):
            await conn.run_sync(_migrate_sqlite_last_read)
        await conn.run_sync(_migrate_conversation_telegram_photo_file_id)
        await conn.run_sync(_migrate_conversation_outbound_lang)
        await conn.run_sync(_migrate_user_workspace_columns)
        await conn.run_sync(_migrate_telegram_webhook_registered_column)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
