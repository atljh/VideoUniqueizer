import asyncio
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from aiogram import Router, F
from aiogram.filters import CommandStart, ChatMemberUpdatedFilter, MEMBER, KICKED
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ChatMemberUpdated, FSInputFile, CallbackQuery
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


async def check_subscription_handler(callback_query: CallbackQuery, button: Button, dialog_manager: DialogManager):
    channel_id = await get_channel_id(callback_query.bot.token)
    if not channel_id:
        return
    member = await callback_query.bot.get_chat_member(chat_id=channel_id, user_id=callback_query.from_user.id)
    if member.status not in ['left', 'kicked']:
        await dialog_manager.done()
        await callback_query.message.answer(
            text='📹 <i>Пожалуйста, отправьте видео, которое вы хотели бы обработать. Размер файла не должен '
                 'превышать 20 МБ.</i>')
    else:
        await callback_query.answer("Подпишитесь, чтобы продолжить.")


async def create_start_dialog(bot_token):
    channel_url = await get_channel_url(bot_token)
    logging.info(f"{bot_token} --- {channel_url}")
    return Dialog(
        Window(
            Const("👇 Подпишитесь на канал:"),
            Column(
                Url(Const("ВСЁ ПРО АРБИТРАЖ ТРАФИКА"), Const(channel_url)),
                Button(Const("✅ Проверить подписку"), id="check_subscription", on_click=check_subscription_handler)
            ),
            state=UserState.checking_subscription
        )
    )


@user_router.message(CommandStart())
async def user_start(message: Message, db, dialog_manager: DialogManager, state: FSMContext):
    await db.sql_create_user(
        user_id=message.from_user.id,
        bot_token=message.bot.token,
        username=message.from_user.username or '',
        fullname=message.from_user.first_name or '',
        is_active=True
    )

    # user_id = message.from_user.id
    # processing = await db.sql_check_user_processing(user_id)
    channel_id = await get_channel_id(message.bot.token)
    if not channel_id:
        return
    member = await message.bot.get_chat_member(chat_id=channel_id, user_id=message.from_user.id)
    if member.status in ['left', 'kicked']:
        await state.set_state(UserState.checking_subscription)
        await dialog_manager.start(
            state=UserState.checking_subscription, mode=StartMode.RESET_STACK
        )
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
            await answer.edit_text(f"Произошла ошибка во время обработки видео: {str(e)}")
            return None


async def handle_video_processing(message, video_file_id, video_path, answer, db):
    global task_queue_count
    loop = asyncio.get_running_loop()
    bot_token = message.bot.token
    output_path = await process_video_async(video_file_id, video_path, answer, loop)
    if output_path:
        try:
            await message.bot.send_video(chat_id=message.chat.id, video=FSInputFile(path=output_path))
            await answer.edit_text("📹 <i>Ваше видео было успешно обработано и отправлено!</i>")
            await message.bot.send_message(chat_id=message.chat.id,
                                           text='📹 <i>Пожалуйста, отправьте видео, которое вы хотели бы обработать. Размер файла не должен превышать 20 МБ.</i>')

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
    task_queue_count -= 1


@user_router.message(MediaGroupFilter(), F.video)
@media_group_handler
async def handle_album(messages: List[Message]):
    for message in messages:
        await message.answer("Пожалуйста, отправьте видео одно за другим, а не в альбоме.")
        return


@user_router.message(F.video)
async def video_customizing(message: Message, db, dialog_manager: DialogManager, state: FSMContext):
    channel_id = await get_channel_id(message.bot.token)
    if not channel_id:
        return
    member = await message.bot.get_chat_member(chat_id=channel_id, user_id=message.from_user.id)
    if member.status in ['left', 'kicked']:
        await state.set_state(UserState.checking_subscription)
        await dialog_manager.start(
            state=UserState.checking_subscription, mode=StartMode.RESET_STACK
        )
        return
    bot_token = message.bot.token
    user_id = message.from_user.id
    processing = await db.sql_check_user_processing(user_id, bot_token)
    if processing == 1:
        await message.answer("Вы уже обрабатываете другое видео. Пожалуйста, подождите, пока оно будет завершено.")
        return
    global task_queue_count
    video_file_id = message.video.file_id
    file_size = message.video.file_size
    duration = message.video.duration

    if file_size > 20 * 1024 * 1024:
        await message.answer("Размер файла превышает 20 МБ. Пожалуйста, отправьте меньший файл.")
        return
    elif duration > 60:
        await message.answer("Длительность видео превышает 60 секунд. Пожалуйста, отправьте более короткое видео.")
        return
    try:
        file = await message.bot.get_file(video_file_id)
    except Exception as e:
        logging.error(e)
        await message.answer("Произошла ошибка при загрузке видео. Пожалуйста, попробуйте снова.")
        return
    await db.sql_set_user_processing(user_id, bot_token, True)
    task_queue_count += 1
    answer = await message.answer(
        f"🔄 Начинаем обработку вашего видео...\nВы №{task_queue_count} в очереди на обработку, ожидайте!")
    video_path = f"videos/{video_file_id}.mp4"
    await message.bot.download(file=file, destination=video_path)

    asyncio.create_task(handle_video_processing(message, video_file_id, video_path, answer, db))


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
