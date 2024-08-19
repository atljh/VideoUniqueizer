from aiogram.fsm.state import StatesGroup, State


class UserState(StatesGroup):
    checking_subscription = State()
