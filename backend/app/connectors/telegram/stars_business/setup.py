"""Dispatcher Stars Business bot."""

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.connectors.telegram.stars_business.handlers_business import router as business_router
from app.connectors.telegram.stars_business.handlers_operator import router as operator_router

stars_business_dp = Dispatcher(storage=MemoryStorage())
stars_business_dp.include_router(business_router)
stars_business_dp.include_router(operator_router)
