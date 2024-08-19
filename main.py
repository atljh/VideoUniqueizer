import asyncio
import logging
import os

import betterlogging as bl
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram_dialog import setup_dialogs

from tgbot.config import load_config
from tgbot.handlers import routers_list
from tgbot.handlers.user import start_dialog
from tgbot.middlewares.config import ConfigMiddleware
from tgbot.middlewares.db import DbMiddleware
from tgbot.db.database import MyDb
from tgbot.filters.admin_filter import admins


def setup_logging():
    log_level = logging.INFO
    log_format = "%(filename)s:%(lineno)d #%(levelname)-8s [%(asctime)s] - %(name)s - %(message)s"
    log_file = "/app/logs/bot.log"  # Путь в контейнере

    if not os.path.exists(log_file):
        with open(log_file, 'w'): pass

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(log_format))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(log_format))

    logging.basicConfig(level=log_level, format=log_format, handlers=[file_handler, console_handler])

    logger = logging.getLogger(__name__)
    logger.info("Starting bot")


async def notify_admins(bot: Bot, admin_ids: list):
    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, "Бот запустился!")
        except Exception as e:
            logging.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")


async def main():
    setup_logging()

    config = load_config(".env")

    bot = Bot(token=config.tg_bot.token, parse_mode=ParseMode.HTML)

    await bot.set_my_commands([
        BotCommand(command="/start", description='Старт')
    ])

    dp = Dispatcher(storage=MemoryStorage())

    dp.include_routers(start_dialog)
    dp.include_routers(*routers_list)
    dp.message.outer_middleware(ConfigMiddleware(config))
    dp.callback_query.outer_middleware(ConfigMiddleware(config))
    dp.message.middleware(DbMiddleware())
    dp.callback_query.middleware(DbMiddleware())
    dp.my_chat_member.middleware(DbMiddleware())

    setup_dialogs(dp)
    await MyDb().db_setup()
    db = MyDb()
    await db.sql_reset_processing_video()
    await notify_admins(bot, admins)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.error("Бот був вимкнений!")
