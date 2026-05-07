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


def _migrate_user_is_platform_admin(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if not insp.has_table("users"):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "is_platform_admin" in cols:
        return
    if sync_conn.dialect.name == "sqlite":
        sync_conn.execute(
            text("ALTER TABLE users ADD COLUMN is_platform_admin BOOLEAN NOT NULL DEFAULT 0")
        )
    else:
        sync_conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN is_platform_admin BOOLEAN NOT NULL DEFAULT false"
            )
        )


def _migrate_studio_generation_refined_prompt(sync_conn) -> None:
    from sqlalchemy import inspect

    insp = inspect(sync_conn)
    if not insp.has_table("studio_generations"):
        return
    cols = {c["name"] for c in insp.get_columns("studio_generations")}
    if "refined_prompt" in cols:
        return
    sync_conn.execute(text("ALTER TABLE studio_generations ADD COLUMN refined_prompt TEXT"))


def _migrate_studio_model_image_kind(sync_conn) -> None:
    from sqlalchemy import inspect

    insp = inspect(sync_conn)
    if not insp.has_table("user_studio_model_images"):
        return
    cols = {c["name"] for c in insp.get_columns("user_studio_model_images")}
    if "image_kind" in cols:
        return
    sync_conn.execute(
        text(
            "ALTER TABLE user_studio_model_images "
            "ADD COLUMN image_kind VARCHAR(24) NOT NULL DEFAULT 'other'"
        )
    )


def _migrate_subscription_billing_plan(sync_conn) -> None:
    from sqlalchemy import inspect

    insp = inspect(sync_conn)
    if not insp.has_table("subscriptions"):
        return
    cols = {c["name"] for c in insp.get_columns("subscriptions")}
    if "billing_plan" in cols:
        return
    sync_conn.execute(
        text(
            "ALTER TABLE subscriptions ADD COLUMN billing_plan VARCHAR(16) NOT NULL DEFAULT 'managed'"
        )
    )


def _migrate_user_studio_model_export_camera(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if not insp.has_table("user_studio_models"):
        return
    cols = {c["name"] for c in insp.get_columns("user_studio_models")}
    dialect = sync_conn.dialect.name
    if "camera_preset_id" not in cols:
        sync_conn.execute(
            text("ALTER TABLE user_studio_models ADD COLUMN camera_preset_id VARCHAR(64)")
        )
    if "export_lat" not in cols:
        if dialect == "sqlite":
            sync_conn.execute(text("ALTER TABLE user_studio_models ADD COLUMN export_lat REAL"))
        else:
            sync_conn.execute(
                text("ALTER TABLE user_studio_models ADD COLUMN export_lat DOUBLE PRECISION")
            )
    if "export_lon" not in cols:
        if dialect == "sqlite":
            sync_conn.execute(text("ALTER TABLE user_studio_models ADD COLUMN export_lon REAL"))
        else:
            sync_conn.execute(
                text("ALTER TABLE user_studio_models ADD COLUMN export_lon DOUBLE PRECISION")
            )
    if "export_selfie" not in cols:
        if dialect == "sqlite":
            sync_conn.execute(
                text(
                    "ALTER TABLE user_studio_models "
                    "ADD COLUMN export_selfie BOOLEAN NOT NULL DEFAULT 0"
                )
            )
        else:
            sync_conn.execute(
                text(
                    "ALTER TABLE user_studio_models "
                    "ADD COLUMN export_selfie BOOLEAN NOT NULL DEFAULT false"
                )
            )


def _migrate_studio_model_image_export_selfie(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if not insp.has_table("user_studio_model_images"):
        return
    cols = {c["name"] for c in insp.get_columns("user_studio_model_images")}
    dialect = sync_conn.dialect.name
    if "export_selfie" in cols:
        return
    if dialect == "sqlite":
        sync_conn.execute(
            text(
                "ALTER TABLE user_studio_model_images "
                "ADD COLUMN export_selfie BOOLEAN NOT NULL DEFAULT 0"
            )
        )
    else:
        sync_conn.execute(
            text(
                "ALTER TABLE user_studio_model_images "
                "ADD COLUMN export_selfie BOOLEAN NOT NULL DEFAULT false"
            )
        )
    sync_conn.execute(
        text(
            "UPDATE user_studio_model_images SET export_selfie = 1 "
            "WHERE lower(image_kind) = 'face'"
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
        await conn.run_sync(_migrate_user_is_platform_admin)
        await conn.run_sync(_migrate_studio_generation_refined_prompt)
        await conn.run_sync(_migrate_studio_model_image_kind)
        await conn.run_sync(_migrate_user_studio_model_export_camera)
        await conn.run_sync(_migrate_studio_model_image_export_selfie)
        await conn.run_sync(_migrate_subscription_billing_plan)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
