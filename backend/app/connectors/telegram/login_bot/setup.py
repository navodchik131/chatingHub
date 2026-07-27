"""Dispatcher login-бота (mobile auth)."""

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.connectors.telegram.login_bot.handlers import router as login_router

login_dp = Dispatcher(storage=MemoryStorage())
login_dp.include_router(login_router)
