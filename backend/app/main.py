from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


def _create_legacy_telegram_bot() -> Bot:
    token = settings.legacy_bot_token.strip()
    proxy = (settings.telegram_proxy or "").strip()
    if proxy:
        session = AiohttpSession(proxy=proxy)
        log.info("Telegram Bot использует прокси (TELEGRAM_PROXY)")
        return Bot(token=token, session=session)
    return Bot(token=token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    log.info("Database URL: %s", settings.database_url)
    bot: Bot | None = None
    polling_task: asyncio.Task[None] | None = None
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
    yield
    if polling_task:
        polling_task.cancel()
        try:
            await polling_task
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
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="spa")
