from aiogram.fsm.state import StatesGroup, State


class SendingState(StatesGroup):
    text = State()
    photo = State()
    send = State()
