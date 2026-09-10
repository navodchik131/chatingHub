from __future__ import annotations

import asyncio
import logging
import os
import stat
from contextlib import asynccontextmanager

import anyio.to_thread
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import router as api_router
from app.api.partner_routes import redirect_router as partner_redirect_router
from app.config import settings
from app.connectors.telegram.setup import dp
from app.connectors.telegram.state import (
    set_bot_dp,
    set_telegram_api_error,
    set_telegram_api_not_configured,
    set_telegram_api_ok,
)
from app.background_loops import (
    spawn_companion_maintenance_tasks,
    spawn_fanvue_poll_task,
    spawn_studio_maintenance_tasks,
)
from app.db.session import init_db
from app.services.email_campaigns import email_campaign_worker_loop
from app.services.startup_security import assert_startup_security

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


class SPAStaticFiles(StaticFiles):
    """
    Starlette StaticFiles(html=True) не подставляет index.html для путей вроде /workspace
    (только для каталогов и 404.html). Для React Router при обновлении страницы нужен fallback.
    """

    async def get_response(self, path: str, scope):  # type: ignore[override]
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if (
                exc.status_code != 404
                or not self.html
                or scope["method"] not in ("GET", "HEAD")
            ):
                raise
            full_path, stat_result = await anyio.to_thread.run_sync(
                self.lookup_path, "index.html"
            )
            if stat_result is not None and stat.S_ISREG(stat_result.st_mode):
                return self.file_response(full_path, stat_result, scope)
            raise


def _create_legacy_telegram_bot() -> Bot:
    token = settings.legacy_bot_token.strip()
    proxy = (settings.telegram_proxy or "").strip()
    if proxy:
        session = AiohttpSession(proxy=proxy)
        log.info("Telegram Bot использует прокси (TELEGRAM_PROXY)")
        return Bot(token=token, session=session)
    return Bot(token=token)


async def _deferred_recover_studio_jobs_on_startup() -> None:
    """Recovery после yield: healthcheck/nginx успевают подняться до тяжёлых studio jobs."""
    await asyncio.sleep(12)
    try:
        from app.services.studio_jobs import recover_studio_jobs_on_startup

        await recover_studio_jobs_on_startup()
    except Exception:
        log.exception("studio jobs startup recovery failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    assert_startup_security()
    await init_db()
    try:
        from app.services.motion_video_outline import assert_ffmpeg_tools_available

        assert_ffmpeg_tools_available()
        log.info("ffmpeg/ffprobe OK for motion outline")
    except Exception as e:
        log.error("ffmpeg/ffprobe unavailable: %s", e)
        raise
    try:
        from app.services.fx_rate import get_usd_rate

        await get_usd_rate()
    except Exception:
        log.warning("Initial CBR USD/RUB fetch failed", exc_info=True)
    log.info("Database URL: %s", settings.database_url)
    bot: Bot | None = None
    polling_task: asyncio.Task[None] | None = None
    background_tasks: list[asyncio.Task[None]] = []
    email_worker_task: asyncio.Task[None] | None = None
    companion_job_worker_task: asyncio.Task[None] | None = None
    exif_bot_polling_task: asyncio.Task[None] | None = None
    ig_bot_polling_task: asyncio.Task[None] | None = None
    login_bot_polling_task: asyncio.Task[None] | None = None
    telegram_user_worker_task: asyncio.Task[None] | None = None
    legacy_tok = settings.legacy_bot_token.strip()
    legacy_uid = settings.legacy_user_id
    if legacy_tok and legacy_uid > 0:
        bot = _create_legacy_telegram_bot()
        set_bot_dp(bot, dp)
        try:
            me = await bot.get_me()
            set_telegram_api_ok(me.username)
            log.info("Telegram API доступен (legacy polling): @%s", me.username)
        except Exception as e:
            set_telegram_api_error(str(e))
            log.error("Нет связи с api.telegram.org (legacy): %s", e)
        polling_task = asyncio.create_task(
            dp.start_polling(
                bot,
                allowed_updates=[
                    "message",
                    "edited_message",
                    "message_reaction",
                ],
            )
        )
        log.info("Telegram legacy polling started for user_id=%s", legacy_uid)
    else:
        set_bot_dp(None, None)
        set_telegram_api_not_configured()
        log.info(
            "Telegram legacy polling выключен. Используйте интеграции + webhook (PUBLIC_APP_URL)."
        )
    background_tasks.extend(spawn_studio_maintenance_tasks())
    fanvue_task = spawn_fanvue_poll_task()
    if fanvue_task is not None:
        background_tasks.append(fanvue_task)
    background_tasks.extend(spawn_companion_maintenance_tasks())
    from app.services.companion_bot.job_queue import (
        companion_job_worker_loop,
        recover_stale_companion_jobs_on_startup,
    )

    if settings.companion_jobs_worker_in_api:
        try:
            recovered = await recover_stale_companion_jobs_on_startup()
            if recovered:
                log.info("Companion jobs recovered on startup: %s", recovered)
        except Exception:
            log.exception("Companion job recovery on startup failed")
        companion_job_worker_task = asyncio.create_task(companion_job_worker_loop())
        log.info("Companion job worker started")
    else:
        companion_job_worker_task = None
        log.info(
            "Companion job worker disabled in API (APP_ROLE=%s)",
            settings.app_role_normalized,
        )
    if settings.exif_bot_token.strip():
        from app.connectors.telegram.exif_bot.bot import run_exif_bot_polling

        exif_bot_polling_task = asyncio.create_task(run_exif_bot_polling())
        log.info("EXIF Telegram bot polling enabled")
    else:
        exif_bot_polling_task = None
        log.info("EXIF bot disabled (set EXIF_BOT_TOKEN to enable)")
    if settings.ig_bot_token.strip():
        from app.connectors.telegram.ig_bot.bot import run_ig_bot_polling

        ig_bot_polling_task = asyncio.create_task(run_ig_bot_polling())
        log.info("Instagram download Telegram bot polling enabled")
    else:
        ig_bot_polling_task = None
        log.info("IG download bot disabled (set IG_BOT_TOKEN to enable)")
    if settings.telegram_login_configured:
        from app.connectors.telegram.login_bot.bot import run_login_bot_polling

        login_bot_polling_task = asyncio.create_task(run_login_bot_polling())
        log.info("Telegram login bot polling enabled")
    else:
        login_bot_polling_task = None
        log.info("Telegram login bot disabled (set TELEGRAM_LOGIN_BOT_TOKEN to enable)")
    if (
        settings.runs_telegram_user_worker
        and settings.telegram_user_worker_enabled
        and settings.telegram_mtproto_configured
    ):
        from app.connectors.telegram_user.worker import telegram_user_worker_loop

        telegram_user_worker_task = asyncio.create_task(telegram_user_worker_loop())
        log.info("Telegram user MTProto worker enabled")
    else:
        telegram_user_worker_task = None
        if not settings.telegram_mtproto_configured:
            log.info("Telegram user MTProto worker disabled (TELEGRAM_API_ID/HASH not set)")
    if settings.smtp_configured:
        email_worker_task = asyncio.create_task(email_campaign_worker_loop())
        log.info("Email campaign worker started (SMTP: %s)", settings.smtp_host)
    else:
        log.info("Email campaigns disabled: SMTP not configured")
    try:
        from app.connectors.telegram.webhook import refresh_registered_telegram_webhooks

        await refresh_registered_telegram_webhooks()
    except Exception:
        log.exception("Telegram webhook refresh on startup failed")
    if settings.app_role_normalized in ("api", "all"):
        asyncio.create_task(_deferred_recover_studio_jobs_on_startup())
    yield
    if polling_task:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
    for task in background_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    if email_worker_task:
        email_worker_task.cancel()
        try:
            await email_worker_task
        except asyncio.CancelledError:
            pass
    if companion_job_worker_task:
        companion_job_worker_task.cancel()
        try:
            await companion_job_worker_task
        except asyncio.CancelledError:
            pass
    if exif_bot_polling_task:
        exif_bot_polling_task.cancel()
        try:
            await exif_bot_polling_task
        except asyncio.CancelledError:
            pass
    if ig_bot_polling_task:
        ig_bot_polling_task.cancel()
        try:
            await ig_bot_polling_task
        except asyncio.CancelledError:
            pass
    if login_bot_polling_task:
        login_bot_polling_task.cancel()
        try:
            await login_bot_polling_task
        except asyncio.CancelledError:
            pass
    if telegram_user_worker_task:
        telegram_user_worker_task.cancel()
        try:
            await telegram_user_worker_task
        except asyncio.CancelledError:
            pass
        from app.connectors.telegram_user.worker import shutdown_telegram_user_worker

        await shutdown_telegram_user_worker()
    if bot:
        await bot.session.close()
        log.info("Telegram bot session closed")


app = FastAPI(title="Chating Hub", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)
app.include_router(partner_redirect_router)

_frontend_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
)
_frontend_dist = None
# Только React SPA (dist-site). Legacy dist/index.html с mm-os-bridge не используем.
_candidate = os.path.join(_frontend_root, "dist-site")
if os.path.isfile(os.path.join(_candidate, "index.html")):
    _frontend_dist = _candidate
else:
    _frontend_dist = None
if _frontend_dist:
    app.mount(
        "/",
        SPAStaticFiles(directory=_frontend_dist, html=True),
        name="spa",
    )
else:
    # Без dist-site в образе api nginx на / отдаёт FastAPI 404 JSON вместо маркетинг-SPA
    log.warning(
        "frontend dist-site not found (%s) — rebuild api image with npm run build:site",
        _candidate,
    )
