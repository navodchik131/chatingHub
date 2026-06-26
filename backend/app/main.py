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
from app.config import settings
from app.connectors.telegram.setup import dp
from app.connectors.telegram.state import (
    set_bot_dp,
    set_telegram_api_error,
    set_telegram_api_not_configured,
    set_telegram_api_ok,
)
from app.db.session import init_db
from app.services.studio_generation_storage import retry_pending_studio_archives
from app.services.studio_generations_retention import purge_studio_generations_expired
from app.services.email_campaigns import email_campaign_worker_loop
from app.services.fanvue_inbox_poll import fanvue_inbox_poll_loop

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


async def _studio_generations_retention_loop() -> None:
    """Первый прогон с задержкой, чтобы не конкурировать со стартом."""
    await asyncio.sleep(120)
    while True:
        try:
            await purge_studio_generations_expired()
        except Exception:
            log.exception("Studio generations retention purge failed")
        await asyncio.sleep(max(3600, settings.studio_generations_retention_interval_hours * 3600))


async def _studio_archive_retry_loop() -> None:
    await asyncio.sleep(90)
    interval = max(60, int(settings.studio_archive_retry_interval_seconds))
    while True:
        try:
            await retry_pending_studio_archives()
        except Exception:
            log.exception("Studio archive retry loop failed")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    log.info("Database URL: %s", settings.database_url)
    bot: Bot | None = None
    polling_task: asyncio.Task[None] | None = None
    retention_task: asyncio.Task[None] | None = None
    archive_retry_task: asyncio.Task[None] | None = None
    fanvue_poll_task: asyncio.Task[None] | None = None
    email_worker_task: asyncio.Task[None] | None = None
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
        polling_task = asyncio.create_task(dp.start_polling(bot))
        log.info("Telegram legacy polling started for user_id=%s", legacy_uid)
    else:
        set_bot_dp(None, None)
        set_telegram_api_not_configured()
        log.info(
            "Telegram legacy polling выключен. Используйте интеграции + webhook (PUBLIC_APP_URL)."
        )
    if settings.studio_generations_retention_days > 0:
        retention_task = asyncio.create_task(_studio_generations_retention_loop())
        log.info(
            "Studio generations retention enabled: %s day(s), every %s h",
            settings.studio_generations_retention_days,
            settings.studio_generations_retention_interval_hours,
        )
    archive_retry_task = asyncio.create_task(_studio_archive_retry_loop())
    log.info(
        "Studio archive retry loop: every %s s",
        settings.studio_archive_retry_interval_seconds,
    )
    if settings.fanvue_inbox_poll_interval_seconds > 0:
        fanvue_poll_task = asyncio.create_task(fanvue_inbox_poll_loop())
        log.info(
            "Fanvue inbox poll: every %s s (max %s chats × %s msgs)",
            settings.fanvue_inbox_poll_interval_seconds,
            settings.fanvue_inbox_poll_max_chats,
            settings.fanvue_inbox_poll_max_messages_per_chat,
        )
    else:
        fanvue_poll_task = None
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
    yield
    if polling_task:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
    if retention_task:
        retention_task.cancel()
        try:
            await retention_task
        except asyncio.CancelledError:
            pass
    if archive_retry_task:
        archive_retry_task.cancel()
        try:
            await archive_retry_task
        except asyncio.CancelledError:
            pass
    if fanvue_poll_task:
        fanvue_poll_task.cancel()
        try:
            await fanvue_poll_task
        except asyncio.CancelledError:
            pass
    if email_worker_task:
        email_worker_task.cancel()
        try:
            await email_worker_task
        except asyncio.CancelledError:
            pass
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

_frontend_dist = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
)
if os.path.isdir(_frontend_dist):
    app.mount(
        "/",
        SPAStaticFiles(directory=_frontend_dist, html=True),
        name="spa",
    )
