import asyncio

from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from tgbot.filters.admin_filter import IsAdmin, admins
from tgbot.states.sending_state import SendingState

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
admin_router = Router()


admin_panel_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✉️ Зробити Розсилку")],
        [KeyboardButton(text="👤 Користувачі")],
    ],
    resize_keyboard=True
)

cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Отмена")],
    ],
    resize_keyboard=True
)

skip_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Пропустити")],
        [KeyboardButton(text="Отмена")],
    ],
    resize_keyboard=True
)

accept_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Підтвердити")],
        [KeyboardButton(text="Отмена")],
    ],
    resize_keyboard=True
)


@admin_router.message(Command('admin'))
async def send_welcome(message: Message, db):
    await db.sql_create_user(
        user_id=message.from_user.id,
        username=message.from_user.username or '',
        fullname=message.from_user.first_name or '',
        is_active=True
    )

    if message.from_user.id in admins:
        await message.reply(text='Admin Panel:',
                            reply_markup=admin_panel_keyboard)


@admin_router.message(IsAdmin(), F.text == "👤 Користувачі")
async def make_sending(message: Message, db):
    users = await db.sql_get_users()
    await message.reply(text=f"👥 |  {len(users)} корист.")


@admin_router.message(IsAdmin(), F.text == "Отмена")
async def cancel_command(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    await bot.send_message(message.from_user.id,
                           text='Вы отменили действия',
                           reply_markup=admin_panel_keyboard)


@admin_router.message(SendingState.photo, F.text == "Пропустити")
async def skip_photo(message: Message, state: FSMContext):
    user_data = await state.get_data()
    text = user_data['text']
    await state.update_data(photo='skip')
    await state.set_state(SendingState.send)
    await message.reply('Вы пропустили добавление фото')
    await message.reply(text=text,
                        reply_markup=accept_keyboard)


@admin_router.message(IsAdmin(), F.text == "✉️ Зробити Розсилку")
async def make_sending(message: Message, state: FSMContext):
    await state.set_state(SendingState.text)
    await message.reply(text="Введите текст сообщения:",
                        reply_markup=cancel_keyboard)


@admin_router.message(SendingState.text)
async def sending_input_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(SendingState.photo)
    await message.reply(text="Отправьте фото:",
                        reply_markup=skip_keyboard)


@admin_router.message(SendingState.photo)
async def sending_input_photo(message: Message, state: FSMContext):
    if message.photo:
        user_data = await state.get_data()
        text = user_data['text']
        photo = message.photo[-1]
        await state.update_data(photo=photo.file_id)
        await state.set_state(SendingState.send)
        await message.reply_photo(photo=photo.file_id,
                                  caption=text,
                                  reply_markup=accept_keyboard)


@admin_router.message(SendingState.send, F.text == 'Підтвердити')
async def sending_process(message: Message, state: FSMContext, bot: Bot, db):
    await message.reply(text='📬 Розсилка почалась!\n\n❗️ Бот повідомить Вас по завершенню.',
                        reply_markup=admin_panel_keyboard)
    users = await db.sql_get_users()
    all_users = await db.sql_get_all_users()
    sent_users = 0
    user_data = await state.get_data()
    photo = user_data['photo']
    text = user_data['text']
    await state.clear()
    try:
        for user_id in users:
            try:
                if photo == 'skip':
                    await bot.send_message(chat_id=user_id, text=text)
                    sent_users += 1
                else:
                    await bot.send_photo(chat_id=user_id, photo=photo, caption=text)
                    sent_users += 1
            except:
                pass
            await asyncio.sleep(0.1)
        for admin in admins:
            await bot.send_message(chat_id=admin,
                                   text=f'✅ Розсилка закінчилася успішно!\n\n✉️ Було відправлено {sent_users}/{len(all_users)} користувачам.')
    except Exception as e:
        for admin in admins:
            await bot.send_message(chat_id=admin,
                                   text=f'Помилка при розсилці!\n\n✉️ Було відправлено {sent_users}/{len(all_users)} користувачам\nПомилка: {e}')
