"""FSM OPERATOR: wizard paid media."""

from aiogram.fsm.state import State, StatesGroup


class OperatorPaidStates(StatesGroup):
    waiting_media = State()
    waiting_star_count = State()
    waiting_recipient = State()
    confirm_send = State()
