"""Dispatcher Instagram download-бота."""

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.connectors.telegram.ig_bot.handlers import router as ig_router

ig_dp = Dispatcher(storage=MemoryStorage())
ig_dp.include_router(ig_router)
