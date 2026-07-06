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
    if "tribute_share_percent" not in cols:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN tribute_share_percent INTEGER"))
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
        await conn.run_sync(_migrate_funnel_events_table)
        await conn.run_sync(_migrate_workflow_workspaces_table)
        await conn.run_sync(_migrate_credit_account_demo_generations)
        await conn.run_sync(_migrate_billing_plans_rename)
        await conn.run_sync(_migrate_trialing_to_credits_demo)
        await conn.run_sync(_migrate_user_email_marketing_opt_out)
        await conn.run_sync(_migrate_email_campaigns_tables)
        await conn.run_sync(_migrate_fanvue_oauth_columns)
        await conn.run_sync(_migrate_fanvue_oauth_states_table)
        await conn.run_sync(_migrate_chat_message_features)
        await conn.run_sync(_migrate_platform_connections_multi)
        await conn.run_sync(_migrate_instagram_connections)
        await conn.run_sync(_migrate_tribute_connections)
        await conn.run_sync(_migrate_conversation_notes)
        await conn.run_sync(_migrate_companion_bot)
        await conn.run_sync(_migrate_conversation_categories)
        await conn.run_sync(_migrate_roadmap_v1)
        await conn.run_sync(_migrate_exif_bot_tables)


def _migrate_conversation_categories(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if not insp.has_table("conversations"):
        return
    cols = {c["name"] for c in insp.get_columns("conversations")}
    dialect = sync_conn.dialect.name
    if "manual_category" not in cols:
        sync_conn.execute(
            text("ALTER TABLE conversations ADD COLUMN manual_category VARCHAR(16)")
        )
    if "is_blocked" not in cols:
        if dialect == "sqlite":
            sync_conn.execute(
                text(
                    "ALTER TABLE conversations ADD COLUMN is_blocked BOOLEAN NOT NULL DEFAULT 0"
                )
            )
        else:
            sync_conn.execute(
                text(
                    "ALTER TABLE conversations ADD COLUMN is_blocked BOOLEAN NOT NULL DEFAULT false"
                )
            )


def _migrate_companion_bot(sync_conn) -> None:
    from sqlalchemy import inspect, text

    from app.db.models import BotResponseEvent, CompanionConversationState

    insp = inspect(sync_conn)
    dialect = sync_conn.dialect.name
    int_def = "INTEGER"

    for table in ("telegram_connections", "fanvue_connections"):
        if not insp.has_table(table):
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if "companion_mode" not in cols:
            sync_conn.execute(
                text(f"ALTER TABLE {table} ADD COLUMN companion_mode VARCHAR(16) DEFAULT 'off'")
            )
        if "companion_delay_min_sec" not in cols:
            sync_conn.execute(
                text(
                    f"ALTER TABLE {table} ADD COLUMN companion_delay_min_sec {int_def} DEFAULT 5"
                )
            )
        if "companion_delay_max_sec" not in cols:
            sync_conn.execute(
                text(
                    f"ALTER TABLE {table} ADD COLUMN companion_delay_max_sec {int_def} DEFAULT 45"
                )
            )
        if "companion_max_replies_per_hour" not in cols:
            sync_conn.execute(
                text(
                    f"ALTER TABLE {table} ADD COLUMN companion_max_replies_per_hour "
                    f"{int_def} DEFAULT 60"
                )
            )

    if not insp.has_table("companion_conversation_states"):
        CompanionConversationState.__table__.create(sync_conn, checkfirst=True)
    if not insp.has_table("bot_response_events"):
        BotResponseEvent.__table__.create(sync_conn, checkfirst=True)

    from app.db.models import CompanionFeedbackReport

    if not insp.has_table("companion_feedback_reports"):
        CompanionFeedbackReport.__table__.create(sync_conn, checkfirst=True)

    from app.db.models import CompanionStyleExample

    if not insp.has_table("companion_style_examples"):
        CompanionStyleExample.__table__.create(sync_conn, checkfirst=True)

    if insp.has_table("conversations"):
        cols = {c["name"] for c in insp.get_columns("conversations")}
        if "companion_mode_override" not in cols:
            sync_conn.execute(
                text("ALTER TABLE conversations ADD COLUMN companion_mode_override VARCHAR(16)")
            )

    if insp.has_table("user_studio_models"):
        cols = {c["name"] for c in insp.get_columns("user_studio_models")}
        if "companion_persona_json" not in cols:
            sync_conn.execute(
                text("ALTER TABLE user_studio_models ADD COLUMN companion_persona_json TEXT")
            )


def _migrate_roadmap_v1(sync_conn) -> None:
    from sqlalchemy import inspect, text

    from app.db.models import ChatterSnippet, CompanionJob

    insp = inspect(sync_conn)
    dialect = sync_conn.dialect.name

    if insp.has_table("conversations"):
        cols = {c["name"] for c in insp.get_columns("conversations")}
        if "assigned_user_id" not in cols:
            sync_conn.execute(
                text("ALTER TABLE conversations ADD COLUMN assigned_user_id INTEGER")
            )
            sync_conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_conversations_assigned_user_id "
                    "ON conversations(assigned_user_id)"
                )
            )

    if not insp.has_table("companion_jobs"):
        CompanionJob.__table__.create(sync_conn, checkfirst=True)
    if not insp.has_table("chatter_snippets"):
        ChatterSnippet.__table__.create(sync_conn, checkfirst=True)


def _migrate_exif_bot_tables(sync_conn) -> None:
    from sqlalchemy import inspect

    from app.db.models import ExifBotProfile, ExifBotUser

    insp = inspect(sync_conn)
    if not insp.has_table("exif_bot_users"):
        ExifBotUser.__table__.create(sync_conn, checkfirst=True)
    if not insp.has_table("exif_bot_profiles"):
        ExifBotProfile.__table__.create(sync_conn, checkfirst=True)
    _migrate_exif_bot_user_daily_limits(sync_conn)


def _migrate_exif_bot_user_daily_limits(sync_conn) -> None:
    import logging

    from sqlalchemy import inspect, text

    log = logging.getLogger(__name__)
    insp = inspect(sync_conn)
    if not insp.has_table("exif_bot_users"):
        return
    cols = {c["name"] for c in insp.get_columns("exif_bot_users")}
    dialect = sync_conn.dialect.name
    if "daily_process_count" not in cols:
        if dialect == "sqlite":
            sync_conn.execute(
                text(
                    "ALTER TABLE exif_bot_users ADD COLUMN daily_process_count INTEGER NOT NULL DEFAULT 0"
                )
            )
        else:
            sync_conn.execute(
                text(
                    "ALTER TABLE exif_bot_users ADD COLUMN daily_process_count INTEGER NOT NULL DEFAULT 0"
                )
            )
    if "daily_process_day" not in cols:
        sync_conn.execute(
            text("ALTER TABLE exif_bot_users ADD COLUMN daily_process_day VARCHAR(10)")
        )
    cols_after = {c["name"] for c in insp.get_columns("exif_bot_users")}
    if "daily_process_count" not in cols_after or "daily_process_day" not in cols_after:
        log.error(
            "exif_bot_users: daily limit columns missing after migration (have %s)",
            sorted(cols_after),
        )
    else:
        log.info("exif_bot_users: daily limit columns OK")


def _migrate_conversation_notes(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if insp.has_table("conversation_notes"):
        return
    dialect = sync_conn.dialect.name
    if dialect == "sqlite":
        sync_conn.execute(
            text(
                """
                CREATE TABLE conversation_notes (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    author_user_id INTEGER,
                    kind VARCHAR(16) NOT NULL,
                    content TEXT NOT NULL,
                    is_pinned BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME,
                    updated_at DATETIME,
                    FOREIGN KEY(conversation_id) REFERENCES conversations (id) ON DELETE CASCADE,
                    FOREIGN KEY(author_user_id) REFERENCES users (id) ON DELETE SET NULL
                )
                """
            )
        )
    else:
        sync_conn.execute(
            text(
                """
                CREATE TABLE conversation_notes (
                    id SERIAL PRIMARY KEY,
                    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    author_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    kind VARCHAR(16) NOT NULL,
                    content TEXT NOT NULL,
                    is_pinned BOOLEAN NOT NULL DEFAULT false,
                    created_at TIMESTAMP WITH TIME ZONE,
                    updated_at TIMESTAMP WITH TIME ZONE
                )
                """
            )
        )
    sync_conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_conversation_notes_conversation_id "
            "ON conversation_notes(conversation_id)"
        )
    )
    sync_conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_conversation_notes_kind "
            "ON conversation_notes(kind)"
        )
    )


def _migrate_platform_connections_multi(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    dialect = sync_conn.dialect.name

    def _add_col(table: str, col_sql: str) -> None:
        if not insp.has_table(table):
            return
        cols = {c["name"] for c in insp.get_columns(table)}
        col_name = col_sql.split()[0]
        if col_name not in cols:
            sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_sql}"))

    for table in ("telegram_connections", "fanvue_connections"):
        if not insp.has_table(table):
            continue
        _add_col(table, "label VARCHAR(128)")
        _add_col(table, "studio_model_id INTEGER")
        if dialect == "postgresql":
            sync_conn.execute(
                text(
                    f"""
                    DO $$ BEGIN
                      ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_user_id_key;
                    EXCEPTION WHEN undefined_object THEN NULL;
                    END $$;
                    """
                )
            )
            sync_conn.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS ix_{table}_user_id ON {table}(user_id)"
                )
            )

    if insp.has_table("conversations"):
        _add_col("conversations", "telegram_connection_id INTEGER")
        _add_col("conversations", "fanvue_connection_id INTEGER")
        sync_conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_conversations_telegram_connection_id "
                "ON conversations(telegram_connection_id)"
            )
        )
        sync_conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_conversations_fanvue_connection_id "
                "ON conversations(fanvue_connection_id)"
            )
        )

    if insp.has_table("fanvue_oauth_states"):
        _add_col("fanvue_oauth_states", "connection_id INTEGER")
        _add_col("fanvue_oauth_states", "label VARCHAR(128)")
        _add_col("fanvue_oauth_states", "studio_model_id INTEGER")

    # Привязать существующие диалоги к единственному подключению пользователя
    if insp.has_table("conversations") and insp.has_table("telegram_connections"):
        sync_conn.execute(
            text(
                """
                UPDATE conversations
                SET telegram_connection_id = (
                    SELECT tc.id FROM telegram_connections tc
                    WHERE tc.user_id = conversations.user_id
                      AND tc.is_active = 1
                    ORDER BY tc.id ASC LIMIT 1
                )
                WHERE platform = 'telegram'
                  AND telegram_connection_id IS NULL
                """
                if dialect == "sqlite"
                else """
                UPDATE conversations c
                SET telegram_connection_id = sub.id
                FROM (
                    SELECT DISTINCT ON (user_id) user_id, id
                    FROM telegram_connections
                    WHERE is_active = true
                    ORDER BY user_id, id ASC
                ) sub
                WHERE c.platform = 'telegram'
                  AND c.user_id = sub.user_id
                  AND c.telegram_connection_id IS NULL
                """
            )
        )
    if insp.has_table("conversations") and insp.has_table("fanvue_connections"):
        sync_conn.execute(
            text(
                """
                UPDATE conversations
                SET fanvue_connection_id = (
                    SELECT fc.id FROM fanvue_connections fc
                    WHERE fc.user_id = conversations.user_id
                      AND fc.creator_uuid = conversations.external_topic_id
                    ORDER BY fc.id ASC LIMIT 1
                )
                WHERE platform = 'fanvue'
                  AND fanvue_connection_id IS NULL
                """
            )
        )
        sync_conn.execute(
            text(
                """
                UPDATE conversations
                SET fanvue_connection_id = (
                    SELECT fc.id FROM fanvue_connections fc
                    WHERE fc.user_id = conversations.user_id
                    ORDER BY fc.id ASC LIMIT 1
                )
                WHERE platform = 'fanvue'
                  AND fanvue_connection_id IS NULL
                """
            )
        )

    # studio_model_id с диалогов → на подключение (если ещё не задано)
    if insp.has_table("fanvue_connections") and insp.has_table("conversations"):
        sync_conn.execute(
            text(
                """
                UPDATE fanvue_connections
                SET studio_model_id = (
                    SELECT c.studio_model_id FROM conversations c
                    WHERE c.fanvue_connection_id = fanvue_connections.id
                      AND c.studio_model_id IS NOT NULL
                    ORDER BY c.updated_at DESC LIMIT 1
                )
                WHERE studio_model_id IS NULL
                """
            )
        )
    if insp.has_table("telegram_connections") and insp.has_table("conversations"):
        sync_conn.execute(
            text(
                """
                UPDATE telegram_connections
                SET studio_model_id = (
                    SELECT c.studio_model_id FROM conversations c
                    WHERE c.telegram_connection_id = telegram_connections.id
                      AND c.studio_model_id IS NOT NULL
                    ORDER BY c.updated_at DESC LIMIT 1
                )
                WHERE studio_model_id IS NULL
                """
            )
        )

    # Диалоги наследуют модель подключения
    if insp.has_table("conversations"):
        sync_conn.execute(
            text(
                """
                UPDATE conversations
                SET studio_model_id = (
                    SELECT fc.studio_model_id FROM fanvue_connections fc
                    WHERE fc.id = conversations.fanvue_connection_id
                )
                WHERE platform = 'fanvue'
                  AND fanvue_connection_id IS NOT NULL
                  AND EXISTS (
                    SELECT 1 FROM fanvue_connections fc
                    WHERE fc.id = conversations.fanvue_connection_id
                      AND fc.studio_model_id IS NOT NULL
                  )
                """
            )
        )
        sync_conn.execute(
            text(
                """
                UPDATE conversations
                SET studio_model_id = (
                    SELECT tc.studio_model_id FROM telegram_connections tc
                    WHERE tc.id = conversations.telegram_connection_id
                )
                WHERE platform = 'telegram'
                  AND telegram_connection_id IS NOT NULL
                  AND EXISTS (
                    SELECT 1 FROM telegram_connections tc
                    WHERE tc.id = conversations.telegram_connection_id
                      AND tc.studio_model_id IS NOT NULL
                  )
                """
            )
        )


def _migrate_instagram_connections(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    dialect = sync_conn.dialect.name

    if not insp.has_table("instagram_connections"):
        if dialect == "sqlite":
            sync_conn.execute(
                text(
                    """
                    CREATE TABLE instagram_connections (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        label VARCHAR(128),
                        studio_model_id INTEGER,
                        instagram_user_id VARCHAR(64) NOT NULL,
                        instagram_username VARCHAR(128),
                        access_token_encrypted TEXT NOT NULL,
                        token_expires_at DATETIME,
                        oauth_connected_at DATETIME,
                        created_at DATETIME,
                        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
                        FOREIGN KEY(studio_model_id) REFERENCES user_studio_models (id) ON DELETE SET NULL
                    )
                    """
                )
            )
        else:
            sync_conn.execute(
                text(
                    """
                    CREATE TABLE instagram_connections (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                        label VARCHAR(128),
                        studio_model_id INTEGER REFERENCES user_studio_models (id) ON DELETE SET NULL,
                        instagram_user_id VARCHAR(64) NOT NULL,
                        instagram_username VARCHAR(128),
                        access_token_encrypted TEXT NOT NULL,
                        token_expires_at TIMESTAMPTZ,
                        oauth_connected_at TIMESTAMPTZ,
                        created_at TIMESTAMPTZ
                    )
                    """
                )
            )
        sync_conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_instagram_connections_user_id "
                "ON instagram_connections(user_id)"
            )
        )
        sync_conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_instagram_connections_instagram_user_id "
                "ON instagram_connections(instagram_user_id)"
            )
        )

    if not insp.has_table("instagram_oauth_states"):
        if dialect == "sqlite":
            sync_conn.execute(
                text(
                    """
                    CREATE TABLE instagram_oauth_states (
                        state VARCHAR(128) NOT NULL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        connection_id INTEGER,
                        label VARCHAR(128),
                        studio_model_id INTEGER,
                        created_at DATETIME,
                        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                    """
                )
            )
        else:
            sync_conn.execute(
                text(
                    """
                    CREATE TABLE instagram_oauth_states (
                        state VARCHAR(128) PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                        connection_id INTEGER,
                        label VARCHAR(128),
                        studio_model_id INTEGER,
                        created_at TIMESTAMPTZ
                    )
                    """
                )
            )
        sync_conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_instagram_oauth_states_user_id "
                "ON instagram_oauth_states(user_id)"
            )
        )

    if insp.has_table("conversations"):
        cols = {c["name"] for c in insp.get_columns("conversations")}
        if "instagram_connection_id" not in cols:
            sync_conn.execute(
                text("ALTER TABLE conversations ADD COLUMN instagram_connection_id INTEGER")
            )
            sync_conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_conversations_instagram_connection_id "
                    "ON conversations(instagram_connection_id)"
                )
            )


def _migrate_tribute_connections(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    dialect = sync_conn.dialect.name

    if not insp.has_table("tribute_connections"):
        if dialect == "sqlite":
            sync_conn.execute(
                text(
                    """
                    CREATE TABLE tribute_connections (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        label VARCHAR(128),
                        studio_model_id INTEGER,
                        api_key_encrypted TEXT NOT NULL,
                        webhook_secret VARCHAR(64) NOT NULL UNIQUE,
                        is_active BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME,
                        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
                        FOREIGN KEY(studio_model_id) REFERENCES user_studio_models (id) ON DELETE SET NULL
                    )
                    """
                )
            )
        else:
            sync_conn.execute(
                text(
                    """
                    CREATE TABLE tribute_connections (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                        label VARCHAR(128),
                        studio_model_id INTEGER REFERENCES user_studio_models (id) ON DELETE SET NULL,
                        api_key_encrypted TEXT NOT NULL,
                        webhook_secret VARCHAR(64) NOT NULL UNIQUE,
                        is_active BOOLEAN NOT NULL DEFAULT true,
                        created_at TIMESTAMPTZ
                    )
                    """
                )
            )
        sync_conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_tribute_connections_user_id "
                "ON tribute_connections(user_id)"
            )
        )
        sync_conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_tribute_connections_studio_model_id "
                "ON tribute_connections(studio_model_id)"
            )
        )

    if not insp.has_table("tribute_earning_events"):
        if dialect == "sqlite":
            sync_conn.execute(
                text(
                    """
                    CREATE TABLE tribute_earning_events (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        tribute_connection_id INTEGER NOT NULL,
                        studio_model_id INTEGER,
                        external_event_id VARCHAR(128) NOT NULL UNIQUE,
                        event_name VARCHAR(64) NOT NULL,
                        amount_minor INTEGER NOT NULL,
                        currency VARCHAR(8) NOT NULL,
                        occurred_at DATETIME NOT NULL,
                        raw_meta TEXT,
                        created_at DATETIME,
                        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
                        FOREIGN KEY(tribute_connection_id) REFERENCES tribute_connections (id) ON DELETE CASCADE,
                        FOREIGN KEY(studio_model_id) REFERENCES user_studio_models (id) ON DELETE SET NULL
                    )
                    """
                )
            )
        else:
            sync_conn.execute(
                text(
                    """
                    CREATE TABLE tribute_earning_events (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
                        tribute_connection_id INTEGER NOT NULL REFERENCES tribute_connections (id) ON DELETE CASCADE,
                        studio_model_id INTEGER REFERENCES user_studio_models (id) ON DELETE SET NULL,
                        external_event_id VARCHAR(128) NOT NULL UNIQUE,
                        event_name VARCHAR(64) NOT NULL,
                        amount_minor INTEGER NOT NULL,
                        currency VARCHAR(8) NOT NULL,
                        occurred_at TIMESTAMPTZ NOT NULL,
                        raw_meta TEXT,
                        created_at TIMESTAMPTZ
                    )
                    """
                )
            )
        sync_conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_tribute_earning_events_user_id "
                "ON tribute_earning_events(user_id)"
            )
        )
        sync_conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_tribute_earning_events_occurred_at "
                "ON tribute_earning_events(occurred_at)"
            )
        )
        sync_conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_tribute_earning_events_studio_model_id "
                "ON tribute_earning_events(studio_model_id)"
            )
        )


def _migrate_chat_message_features(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    dialect = sync_conn.dialect.name
    bool_def = "0" if dialect == "sqlite" else "false"
    if insp.has_table("conversations"):
        cols = {c["name"] for c in insp.get_columns("conversations")}
        if "auto_translate_disabled" not in cols:
            sync_conn.execute(
                text(
                    f"ALTER TABLE conversations "
                    f"ADD COLUMN auto_translate_disabled BOOLEAN NOT NULL DEFAULT {bool_def}"
                )
            )
    if not insp.has_table("messages"):
        return
    cols = {c["name"] for c in insp.get_columns("messages")}
    if "reply_to_message_id" not in cols:
        sync_conn.execute(
            text("ALTER TABLE messages ADD COLUMN reply_to_message_id INTEGER")
        )
    if "platform_message_id" not in cols:
        sync_conn.execute(
            text("ALTER TABLE messages ADD COLUMN platform_message_id VARCHAR(128)")
        )
    if "reactions_json" not in cols:
        sync_conn.execute(text("ALTER TABLE messages ADD COLUMN reactions_json TEXT"))
    if "sender_user_id" not in cols:
        sync_conn.execute(text("ALTER TABLE messages ADD COLUMN sender_user_id INTEGER"))


def _migrate_fanvue_oauth_columns(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if not insp.has_table("fanvue_connections"):
        return
    cols = {c["name"]: c for c in insp.get_columns("fanvue_connections")}
    if "refresh_token_encrypted" not in cols:
        sync_conn.execute(text("ALTER TABLE fanvue_connections ADD COLUMN refresh_token_encrypted TEXT"))
    if "token_expires_at" not in cols:
        sync_conn.execute(
            text("ALTER TABLE fanvue_connections ADD COLUMN token_expires_at TIMESTAMP")
        )
    if "oauth_connected_at" not in cols:
        sync_conn.execute(
            text("ALTER TABLE fanvue_connections ADD COLUMN oauth_connected_at TIMESTAMP")
        )
    sign_col = cols.get("webhook_signing_secret_encrypted")
    if sign_col is not None and not sign_col.get("nullable", True):
        dialect = sync_conn.dialect.name
        if dialect != "sqlite":
            sync_conn.execute(
                text(
                    "ALTER TABLE fanvue_connections "
                    "ALTER COLUMN webhook_signing_secret_encrypted DROP NOT NULL"
                )
            )


def _migrate_fanvue_oauth_states_table(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if insp.has_table("fanvue_oauth_states"):
        return
    sync_conn.execute(
        text(
            """
            CREATE TABLE fanvue_oauth_states (
                state VARCHAR(128) PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                code_verifier VARCHAR(128) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    sync_conn.execute(
        text("CREATE INDEX IF NOT EXISTS ix_fanvue_oauth_states_user_id ON fanvue_oauth_states(user_id)")
    )


def _migrate_credit_account_demo_generations(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if not insp.has_table("credit_accounts"):
        return
    cols = {c["name"] for c in insp.get_columns("credit_accounts")}
    if "demo_generations_remaining" not in cols:
        sync_conn.execute(
            text(
                "ALTER TABLE credit_accounts "
                "ADD COLUMN demo_generations_remaining INTEGER NOT NULL DEFAULT 0"
            )
        )


def _migrate_billing_plans_rename(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if not insp.has_table("subscriptions"):
        return
    sync_conn.execute(
        text("UPDATE subscriptions SET billing_plan = 'standard' WHERE billing_plan = 'managed'")
    )
    sync_conn.execute(
        text("UPDATE subscriptions SET billing_plan = 'pro' WHERE billing_plan = 'byok'")
    )


def _migrate_trialing_to_credits_demo(sync_conn) -> None:
    """Пробные без оплат → Credits, 3 демо, баланс 0."""
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if not insp.has_table("credit_accounts") or not insp.has_table("subscriptions"):
        return
    cols = {c["name"] for c in insp.get_columns("credit_accounts")}
    if "demo_generations_remaining" not in cols:
        return
    paid_kinds = (
        "yookassa_credits_pack",
        "managed_subscription_bonus",
        "standard_subscription_bonus",
        "subscription_credits_payment",
    )
    ph = ", ".join(f"'{k}'" for k in paid_kinds)
    sync_conn.execute(
        text(
            f"""
            UPDATE subscriptions SET billing_plan = 'credits', status = 'none'
            WHERE status = 'trialing'
              AND user_id NOT IN (
                SELECT DISTINCT user_id FROM usage_events WHERE kind IN ({ph})
              )
            """
        )
    )
    sync_conn.execute(
        text(
            f"""
            UPDATE credit_accounts
            SET demo_generations_remaining = 3, balance = 0
            WHERE demo_generations_remaining = 0
              AND user_id IN (
                SELECT user_id FROM subscriptions
                WHERE billing_plan = 'credits' AND status = 'none'
              )
              AND user_id NOT IN (
                SELECT DISTINCT user_id FROM usage_events WHERE kind IN ({ph})
              )
            """
        )
    )


def _migrate_workflow_workspaces_table(sync_conn) -> None:
    from sqlalchemy import inspect

    from app.db.models import WorkflowWorkspace

    insp = inspect(sync_conn)
    if insp.has_table("workflow_workspaces"):
        return
    WorkflowWorkspace.__table__.create(sync_conn, checkfirst=True)


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


def _migrate_funnel_events_table(sync_conn) -> None:
    from sqlalchemy import inspect

    insp = inspect(sync_conn)
    if insp.has_table("funnel_events"):
        return
    if sync_conn.dialect.name == "sqlite":
        sync_conn.execute(
            text(
                """
                CREATE TABLE funnel_events (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    event VARCHAR(64) NOT NULL,
                    meta TEXT,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """
            )
        )
    else:
        from app.db.models import FunnelEvent

        FunnelEvent.__table__.create(sync_conn, checkfirst=True)
        return
    sync_conn.execute(
        text("CREATE INDEX ix_funnel_events_owner_id ON funnel_events (owner_id)")
    )
    sync_conn.execute(
        text("CREATE INDEX ix_funnel_events_event ON funnel_events (event)")
    )
    sync_conn.execute(
        text("CREATE INDEX ix_funnel_events_created_at ON funnel_events (created_at)")
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


def _migrate_user_email_marketing_opt_out(sync_conn) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(sync_conn)
    if not insp.has_table("users"):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "email_marketing_opt_out" in cols:
        return
    dialect = sync_conn.dialect.name
    if dialect == "sqlite":
        sync_conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN email_marketing_opt_out BOOLEAN NOT NULL DEFAULT 0"
            )
        )
    else:
        sync_conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN email_marketing_opt_out BOOLEAN NOT NULL DEFAULT false"
            )
        )


def _migrate_email_campaigns_tables(sync_conn) -> None:
    from sqlalchemy import inspect

    from app.db.models import EmailCampaign, EmailCampaignRecipient

    insp = inspect(sync_conn)
    if not insp.has_table("email_campaigns"):
        EmailCampaign.__table__.create(sync_conn, checkfirst=True)
    if not insp.has_table("email_campaign_recipients"):
        EmailCampaignRecipient.__table__.create(sync_conn, checkfirst=True)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
