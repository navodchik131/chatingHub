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


def _create_telegram_bot() -> Bot:
    token = settings.bot_token
    proxy = (settings.telegram_proxy or "").strip()
    if proxy:
        session = AiohttpSession(proxy=proxy)
        log.info("Telegram Bot использует прокси (TELEGRAM_PROXY)")
        return Bot(token=token, session=session)
    return Bot(token=token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    log.info("SQLite: %s", settings.database_url)
    bot: Bot | None = None
    polling_task: asyncio.Task[None] | None = None
    if settings.bot_token:
        bot = _create_telegram_bot()
        set_bot_dp(bot, dp)
        try:
            me = await bot.get_me()
            set_telegram_api_ok(me.username)
            log.info("Telegram API доступен: @%s", me.username)
        except Exception as e:
            set_telegram_api_error(str(e))
            log.error(
                "Нет связи с api.telegram.org: %s. "
                "Сообщения в бота не будут приходить, пока не заработает HTTPS к Telegram "
                "(VPN, другая сеть, или TELEGRAM_PROXY в .env — см. README).",
                e,
            )
        polling_task = asyncio.create_task(dp.start_polling(bot))
        log.info("Telegram polling task started")
    else:
        set_bot_dp(None, None)
        set_telegram_api_not_configured()
        log.warning("BOT_TOKEN empty — polling disabled, only API/UI for development")
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

# Одна команда: сборка фронта (npm run build) → отдаём SPA с того же порта
_frontend_dist = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
)
if os.path.isdir(_frontend_dist):
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="spa")
