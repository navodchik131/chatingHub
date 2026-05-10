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
from app.services.studio_generations_retention import purge_studio_generations_expired

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    log.info("Database URL: %s", settings.database_url)
    bot: Bot | None = None
    polling_task: asyncio.Task[None] | None = None
    retention_task: asyncio.Task[None] | None = None
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
