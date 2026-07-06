"""Dispatcher EXIF-бота."""

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.connectors.telegram.exif_bot.handlers import router as exif_router

exif_dp = Dispatcher(storage=MemoryStorage())
exif_dp.include_router(exif_router)
