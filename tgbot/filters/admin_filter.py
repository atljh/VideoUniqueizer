from abc import ABC

from aiogram import types
from aiogram.filters import Filter
from aiogram.types import Message

admins = [1993309130, 972847950]  # @nomiss7
chat_id = -0


class IsAdmin(Filter):
    def __init__(self) -> None:
        pass

    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in admins
