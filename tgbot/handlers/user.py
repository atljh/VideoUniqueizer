import asyncio
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from aiogram import Router, F, Bot, types
from aiogram.filters import CommandStart, ChatMemberUpdatedFilter, MEMBER, KICKED
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ChatMemberUpdated, FSInputFile, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram_dialog import Dialog, DialogManager, Window, StartMode
from aiogram_dialog.widgets.kbd import Button, Url, Column
from aiogram_dialog.widgets.text import Const

from aiogram_media_group import media_group_handler, MediaGroupFilter

from moviepy.editor import VideoFileClip, CompositeVideoClip, ImageClip
import moviepy.video.fx.all as vfx
from typing import List

from tgbot.states.sub_state import UserState
from tgbot.config import load_config


user_router = Router()
executor = ThreadPoolExecutor(max_workers=1)
semaphore = asyncio.Semaphore(1)
config = load_config(".env")

task_queue_count = 0


async def get_channel_id(bot_token):
    for bot_config in config.bots:
        if bot_token == bot_config.token:
            return bot_config.channel_id
    return None


async def get_channel_url(bot_token):
    for bot_config in config.bots:
        if bot_token == bot_config.token:
            return bot_config.channel_url
    return None


@user_router.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription_handler(callback_query: types.CallbackQuery):
    channel_id = await get_channel_id(callback_query.bot.token)
    
    if not channel_id:
        return

    member = await callback_query.bot.get_chat_member(chat_id=channel_id, user_id=callback_query.from_user.id)

    if member.status not in ['left', 'kicked']:
        await callback_query.message.answer(
            "📹 <i>Пожалуйста, отправьте видео, которое вы хотели бы обработать. "
            "Размер файла не должен превышать 20 МБ.</i>", parse_mode="HTML"
        )
    else:
        await callback_query.answer("Подпишитесь, чтобы продолжить.", show_alert=True)



@user_router.message(CommandStart())
async def user_start(message: Message, db, dialog_manager: DialogManager, state: FSMContext):
        
    await db.sql_create_user(
        user_id=message.from_user.id,
        bot_token=message.bot.token,
        username=message.from_user.username or '',
        fullname=message.from_user.first_name or '',
        is_active=True
    )


    channel_id = await get_channel_id(message.bot.token)
    channel_url = await get_channel_url(message.bot.token)
    if not channel_id:
        return
    member = await message.bot.get_chat_member(chat_id=channel_id, user_id=message.from_user.id)
    if member.status in ['left', 'kicked']:
        await state.set_state(UserState.checking_subscription)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="ВСЁ ПРО АРБИТРАЖ ТРАФИКА", url=channel_url)],
                [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subscription")]
            ]
        )
        await message.answer("👇 Подпишитесь на канал:", reply_markup=keyboard)
    else:
        await message.answer(
            text='📹 <i>Пожалуйста, отправьте видео, которое вы хотели бы обработать. Размер файла не должен превышать 20 МБ.</i>')


async def process_video_async(video_file_id, video_path, answer, loop):
    async with semaphore:
        try:
            await asyncio.sleep(1)
            await answer.edit_text("🔄 Разбираем видео на кадры...")
            await asyncio.sleep(1)
            clip = await loop.run_in_executor(executor, VideoFileClip, video_path)

            await answer.edit_text("🔄 Уникализируем каждый кадр...")
            await asyncio.sleep(1)
            clip = await loop.run_in_executor(executor, clip.fx, vfx.speedx, 1.02)

            await answer.edit_text("🔄 Изменяем цветовую гамму...")
            await asyncio.sleep(1)
            clip = await loop.run_in_executor(executor, clip.fx, vfx.colorx, 1.25)

            await answer.edit_text("🔄 Накладываем уникализирующую сетку...")
            await asyncio.sleep(1)
            logo = await loop.run_in_executor(executor, ImageClip, "videos/1.png")
            logo = logo.set_duration(clip.duration).resize(width=clip.size[0], height=clip.size[1]).set_position(
                "center")

            final_clip = CompositeVideoClip([clip, logo])
            output_path = f"videos/processed_{video_file_id}.mp4"
            await answer.edit_text("🔄 Собираем кадры в видео с другим битрейтом...")
            await asyncio.sleep(1)
            await answer.edit_text("🔄 Чистим метаданные, меняем исходный код видео. Это займет 1-4 минуты...")
            await asyncio.sleep(1)
            video_write_func = partial(final_clip.write_videofile, output_path, codec='libx264', preset='slow',
                                       bitrate='5000k')
            await loop.run_in_executor(executor, video_write_func)

            clip.close()
            logo.close()
            return output_path
        except Exception as e:
            logging.error(e)
            await answer.answer(f"Произошла ошибка во время обработки видео")
            return None

@user_router.message(MediaGroupFilter(), F.video)
@media_group_handler
async def handle_album(messages: List[Message]):
    for message in messages:
        await message.answer("Пожалуйста, отправьте видео одно за другим, а не в альбоме.")
        return


task_queue = []
queue_lock = asyncio.Lock()


@user_router.message(F.video)
async def video_customizing(message: Message, db, dialog_manager: DialogManager, state: FSMContext):
    user_id = message.from_user.id
    bot_token = message.bot.token

    processing = await db.sql_check_user_processing(user_id, bot_token)
    if processing == 1:
        await message.answer("Вы уже обрабатываете другое видео. Дождитесь завершения.")
        return

    video_file_id = message.video.file_id
    file_size = message.video.file_size
    duration = message.video.duration

    if file_size > 20 * 1024 * 1024:
        await message.answer("Файл слишком большой (максимум 20 МБ).")
        return
    elif duration > 60:
        await message.answer("Видео не должно быть длиннее 60 секунд.")
        return

    try:
        file = await message.bot.get_file(video_file_id)
    except Exception as e:
        logging.error(e)
        await message.answer("Ошибка при загрузке видео. Попробуйте снова.")
        return

    async with queue_lock:
        task_queue.append({"user_id": user_id, "file_id": video_file_id})
        position = len(task_queue)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить позицию", callback_data="update_queue_position")]
        ]
    )

    answer = await message.answer(
        f"🔄 Начинаем обработку...\nВы №{position} в очереди, ожидайте!",
        reply_markup=keyboard
    )

    video_path = f"videos/{video_file_id}.mp4"
    await message.bot.download(file=file, destination=video_path)

    # Начинаем обработку видео в фоне
    asyncio.create_task(handle_video_processing(message, video_file_id, video_path, answer, db))


@user_router.callback_query(lambda c: c.data == "update_queue_position")
async def update_queue_position(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id

    async with queue_lock:
        position = next((i + 1 for i, task in enumerate(task_queue) if task["user_id"] == user_id), None)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить позицию", callback_data="update_queue_position")]
        ]
    )
    if position is None:
        await callback_query.answer("Вы не в очереди или ваша задача уже обработана.")
    else:
        try:
            await callback_query.message.edit_text(f"🔄 Ваша позиция в очереди: {position}", reply_markup=keyboard)
        except Exception:
            await callback_query.message.edit_text(f"🔄 Ваша позиция в очереди {position}", reply_markup=keyboard)


async def handle_video_processing(message, video_file_id, video_path, answer, db):
    global task_queue

    loop = asyncio.get_running_loop()
    bot_token = message.bot.token

    output_path = await process_video_async(video_file_id, video_path, answer, loop)

    if output_path:
        try:
            await message.bot.send_video(chat_id=message.chat.id, video=FSInputFile(path=output_path))
            await answer.edit_text("📹 <i>Ваше видео было успешно обработано и отправлено!</i>")
            await message.bot.send_message(chat_id=message.chat.id,
                                           text='📹 <i>Пожалуйста, отправьте видео, которое вы хотели бы обработать. '
                                                'Размер файла не должен превышать 20 МБ.</i>')
        except Exception as e:
            await message.answer("Произошла ошибка при отправке видео. Попробуйте позже...")
            print(e)
        finally:
            await db.sql_set_user_processing(message.from_user.id, bot_token, False)
    else:
        await message.answer("Произошла ошибка при обработке видео. Попробуйте позже...")

    os.remove(video_path)
    if output_path:
        os.remove(output_path)

    async with queue_lock:
        task_queue = [task for task in task_queue if task["file_id"] != video_file_id]


@user_router.my_chat_member(
    ChatMemberUpdatedFilter(member_status_changed=KICKED)
)
async def user_blocked_bot(event: ChatMemberUpdated, db):
    bot_token = event.bot.token
    await db.sql_update_user_status(is_active=False, user_id=event.from_user.id, bot_token=bot_token)


@user_router.my_chat_member(
    ChatMemberUpdatedFilter(member_status_changed=MEMBER)
)
async def user_unblocked_bot(event: ChatMemberUpdated, db):
    bot_token = event.bot.token
    await db.sql_update_user_status(is_active=True, user_id=event.from_user.id, bot_token=bot_token)
