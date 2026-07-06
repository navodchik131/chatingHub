"""FSM-состояния EXIF-бота."""

from aiogram.fsm.state import State, StatesGroup


class ExifBotStates(StatesGroup):
    create_name = State()
    create_preset = State()
    create_selfie = State()
    create_main = State()
    create_geo = State()
    waiting_photo = State()
