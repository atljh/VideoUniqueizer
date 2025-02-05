from abc import ABC

from aiogram.filters import Filter
from aiogram.types import Message
from tgbot.config import load_config

config = load_config()

admins = config.tg_bot.admins_id


class IsAdmin(Filter):
    def __init__(self) -> None:
        pass

    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in admins
