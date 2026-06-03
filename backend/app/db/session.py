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


def _migrate_studio_generation_motion_video_prompt(sync_conn) -> None:
    from sqlalchemy import inspect

    insp = inspect(sync_conn)
    if not insp.has_table("studio_generations"):
        return
    cols = {c["name"] for c in insp.get_columns("studio_generations")}
    if "motion_video_prompt_auto" in cols:
        return
    sync_conn.execute(
        text("ALTER TABLE studio_generations ADD COLUMN motion_video_prompt_auto TEXT")
    )


def _migrate_studio_generation_exif_camera(sync_conn) -> None:
    from sqlalchemy import inspect

    insp = inspect(sync_conn)
    if not insp.has_table("studio_generations"):
        return
    cols = {c["name"] for c in insp.get_columns("studio_generations")}
    if "exif_camera" in cols:
        return
    sync_conn.execute(
        text(
            "ALTER TABLE studio_generations "
            "ADD COLUMN exif_camera VARCHAR(16) NOT NULL DEFAULT 'main'"
        )
    )


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


def _migrate_user_referral_columns(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if not insp.has_table("users"):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "referral_code" not in cols:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN referral_code VARCHAR(16)"))
    if "referred_by_user_id" not in cols:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN referred_by_user_id INTEGER"))


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


def _migrate_subscription_plan_tier(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if not insp.has_table("subscriptions"):
        return
    cols = {c["name"] for c in insp.get_columns("subscriptions")}
    if "plan_tier" in cols:
        return
    sync_conn.execute(text("ALTER TABLE subscriptions ADD COLUMN plan_tier VARCHAR(64)"))


def _migrate_wavespeed_connections_table(sync_conn) -> None:
    from sqlalchemy import inspect

    from app.db.models import WavespeedConnection

    insp = inspect(sync_conn)
    if insp.has_table("wavespeed_connections"):
        return
    WavespeedConnection.__table__.create(sync_conn, checkfirst=True)


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
    if dialect == "sqlite":
        sync_conn.execute(
            text(
                "UPDATE user_studio_model_images SET export_selfie = 1 "
                "WHERE lower(image_kind) = 'face'"
            )
        )
    else:
        sync_conn.execute(
            text(
                "UPDATE user_studio_model_images SET export_selfie = true "
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
        await conn.run_sync(_migrate_studio_generation_motion_video_prompt)
        await conn.run_sync(_migrate_studio_generation_exif_camera)
        await conn.run_sync(_migrate_studio_model_image_kind)
        await conn.run_sync(_migrate_user_studio_model_export_camera)
        await conn.run_sync(_migrate_user_studio_model_phone_exif_refs)
        await conn.run_sync(_migrate_studio_model_image_export_selfie)
        await conn.run_sync(_migrate_subscription_billing_plan)
        await conn.run_sync(_migrate_subscription_plan_tier)
        await conn.run_sync(_migrate_user_referral_columns)
        await conn.run_sync(_migrate_wavespeed_connections_table)
        await conn.run_sync(_migrate_studio_jobs_table)
        await conn.run_sync(_migrate_studio_generation_pipeline_phase_a)
        await conn.run_sync(_migrate_studio_motion_render_model_link)
        await conn.run_sync(_migrate_workspace_member_studio_models)
        await conn.run_sync(_migrate_conversation_studio_model_id)
        await conn.run_sync(_migrate_message_attachments_table)


def _migrate_user_studio_model_phone_exif_refs(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if not insp.has_table("user_studio_models"):
        return
    cols = {c["name"] for c in insp.get_columns("user_studio_models")}
    if "phone_exif_selfie_json" not in cols:
        sync_conn.execute(
            text("ALTER TABLE user_studio_models ADD COLUMN phone_exif_selfie_json TEXT")
        )
    if "phone_exif_main_json" not in cols:
        sync_conn.execute(
            text("ALTER TABLE user_studio_models ADD COLUMN phone_exif_main_json TEXT")
        )


def _migrate_message_attachments_table(sync_conn) -> None:
    from sqlalchemy import inspect

    insp = inspect(sync_conn)
    if insp.has_table("message_attachments"):
        return
    sync_conn.execute(
        text(
            """
            CREATE TABLE message_attachments (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                kind VARCHAR(16) NOT NULL DEFAULT 'image',
                relative_path VARCHAR(512) NOT NULL,
                mime_type VARCHAR(64) NOT NULL DEFAULT 'image/jpeg',
                width INTEGER,
                height INTEGER,
                created_at DATETIME NOT NULL,
                FOREIGN KEY(message_id) REFERENCES messages (id) ON DELETE CASCADE
            )
            """
        )
    )
    sync_conn.execute(
        text("CREATE INDEX ix_message_attachments_message_id ON message_attachments (message_id)")
    )


def _migrate_workspace_member_studio_models(sync_conn) -> None:
    from sqlalchemy import inspect

    insp = inspect(sync_conn)
    if insp.has_table("workspace_member_studio_models"):
        return
    if sync_conn.dialect.name == "sqlite":
        sync_conn.execute(
            text(
                """
                CREATE TABLE workspace_member_studio_models (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    member_user_id INTEGER NOT NULL,
                    studio_model_id INTEGER NOT NULL,
                    FOREIGN KEY(member_user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY(studio_model_id) REFERENCES user_studio_models (id) ON DELETE CASCADE,
                    UNIQUE (member_user_id, studio_model_id)
                )
                """
            )
        )
        sync_conn.execute(
            text(
                "CREATE INDEX ix_wmsm_member_user_id "
                "ON workspace_member_studio_models (member_user_id)"
            )
        )
        sync_conn.execute(
            text(
                "CREATE INDEX ix_wmsm_studio_model_id "
                "ON workspace_member_studio_models (studio_model_id)"
            )
        )
    else:
        from app.db.models import WorkspaceMemberStudioModel

        WorkspaceMemberStudioModel.__table__.create(sync_conn, checkfirst=True)


def _migrate_conversation_studio_model_id(sync_conn) -> None:
    from sqlalchemy import inspect

    insp = inspect(sync_conn)
    if not insp.has_table("conversations"):
        return
    cols = {c["name"] for c in insp.get_columns("conversations")}
    if "studio_model_id" not in cols:
        sync_conn.execute(
            text("ALTER TABLE conversations ADD COLUMN studio_model_id INTEGER")
        )
        sync_conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_conversations_studio_model_id "
                "ON conversations(studio_model_id)"
            )
        )


def _migrate_studio_motion_render_model_link(sync_conn) -> None:
    from sqlalchemy import inspect

    insp = inspect(sync_conn)
    if not insp.has_table("studio_motion_renders"):
        return
    col_map = {c["name"]: c for c in insp.get_columns("studio_motion_renders")}
    dialect = sync_conn.dialect.name

    if "studio_model_id" not in col_map:
        if dialect == "sqlite":
            sync_conn.execute(
                text(
                    """
                    CREATE TABLE studio_motion_renders_new (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        studio_generation_id INTEGER,
                        studio_model_id INTEGER,
                        video_url TEXT NOT NULL,
                        created_at DATETIME,
                        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
                        FOREIGN KEY(studio_generation_id) REFERENCES studio_generations (id) ON DELETE SET NULL,
                        FOREIGN KEY(studio_model_id) REFERENCES user_studio_models (id) ON DELETE SET NULL
                    )
                    """
                )
            )
            sync_conn.execute(
                text(
                    """
                    INSERT INTO studio_motion_renders_new
                        (id, user_id, studio_generation_id, video_url, created_at)
                    SELECT id, user_id, studio_generation_id, video_url, created_at
                    FROM studio_motion_renders
                    """
                )
            )
            sync_conn.execute(text("DROP TABLE studio_motion_renders"))
            sync_conn.execute(text("ALTER TABLE studio_motion_renders_new RENAME TO studio_motion_renders"))
        else:
            sync_conn.execute(
                text("ALTER TABLE studio_motion_renders ADD COLUMN studio_model_id INTEGER")
            )

    gen_col = col_map.get("studio_generation_id")
    if gen_col is not None and not gen_col.get("nullable", True) and dialect != "sqlite":
        sync_conn.execute(
            text(
                "ALTER TABLE studio_motion_renders "
                "ALTER COLUMN studio_generation_id DROP NOT NULL"
            )
        )


def _migrate_studio_generation_pipeline_phase_a(sync_conn) -> None:
    from sqlalchemy import inspect

    insp = inspect(sync_conn)
    if not insp.has_table("studio_generations"):
        return
    cols = {c["name"] for c in insp.get_columns("studio_generations")}
    if "status" not in cols:
        sync_conn.execute(
            text(
                "ALTER TABLE studio_generations "
                "ADD COLUMN status VARCHAR(32) NOT NULL DEFAULT 'ready'"
            )
        )
    if "studio_job_id" not in cols:
        sync_conn.execute(
            text("ALTER TABLE studio_generations ADD COLUMN studio_job_id INTEGER")
        )
    if "wavespeed_task_id" not in cols:
        sync_conn.execute(
            text("ALTER TABLE studio_generations ADD COLUMN wavespeed_task_id VARCHAR(128)")
        )
    if "error_message" not in cols:
        sync_conn.execute(text("ALTER TABLE studio_generations ADD COLUMN error_message TEXT"))
    if "error_step" not in cols:
        sync_conn.execute(
            text("ALTER TABLE studio_generations ADD COLUMN error_step VARCHAR(32)")
        )
    sync_conn.execute(
        text(
            "UPDATE studio_generations SET status = 'ready' "
            "WHERE status IS NULL OR trim(status) = ''"
        )
    )
    sync_conn.execute(
        text(
            "UPDATE studio_generations SET status = 'ready' "
            "WHERE trim(COALESCE(relative_path, '')) != '' "
            "AND status NOT IN ('ready', 'failed')"
        )
    )


def _migrate_studio_jobs_table(sync_conn) -> None:
    from sqlalchemy import inspect

    insp = inspect(sync_conn)
    if insp.has_table("studio_jobs"):
        return
    if sync_conn.dialect.name == "sqlite":
        sync_conn.execute(
            text(
                """
                CREATE TABLE studio_jobs (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    actor_user_id INTEGER NOT NULL,
                    job_type VARCHAR(64) NOT NULL,
                    status VARCHAR(16) NOT NULL DEFAULT 'pending',
                    params_json TEXT NOT NULL DEFAULT '{}',
                    result_json TEXT,
                    error_message TEXT,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    started_at DATETIME,
                    completed_at DATETIME,
                    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """
            )
        )
        sync_conn.execute(text("CREATE INDEX ix_studio_jobs_user_id ON studio_jobs (user_id)"))
        sync_conn.execute(text("CREATE INDEX ix_studio_jobs_job_type ON studio_jobs (job_type)"))
        sync_conn.execute(text("CREATE INDEX ix_studio_jobs_status ON studio_jobs (status)"))
    else:
        from app.db.models import StudioJob

        StudioJob.__table__.create(sync_conn, checkfirst=True)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
