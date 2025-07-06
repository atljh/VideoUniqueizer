import asyncio
import os
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import time
from typing import Optional, Dict

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

PROCESSING_TIMEOUT = 300
DOWNLOAD_TIMEOUT = 60

user_router = Router()
executor = ThreadPoolExecutor(max_workers=1)
semaphore = asyncio.Semaphore(1)
config = load_config(".env")

task_queue = []
queue_lock = asyncio.Lock()
active_tasks: Dict[str, threading.Thread] = {}


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


async def update_status(answer: Message, text: str):
    try:
        await answer.edit_text(text)
    except Exception as e:
        logging.error(f"Error updating status: {e}")


def cancel_stuck_task(video_file_id: str):
    if video_file_id in active_tasks:
        thread = active_tasks[video_file_id]
        try:
            thread._Thread__stop()
            logging.warning(f"Принудительно завершен поток для видео {video_file_id}")
        except Exception as e:
            logging.error(f"Ошибка при остановке потока: {e}")
        finally:
            active_tasks.pop(video_file_id, None)


async def process_video_async(video_file_id: str, video_path: str, answer: Message, loop: asyncio.AbstractEventLoop):
    async with semaphore:
        try:
            future = loop.run_in_executor(
                executor, 
                partial(process_video_sync, video_file_id, video_path, answer, loop)
            )
            return await asyncio.wait_for(future, timeout=PROCESSING_TIMEOUT)
        except asyncio.TimeoutError:
            logging.error(f"Timeout processing video {video_file_id}")
            cancel_stuck_task(video_file_id)
            await update_status(answer, "⛔ Видео слишком долго обрабатывается. Проверьте, что оно не повреждено.")
            raise
        except Exception as e:
            logging.error(f"Error processing video {video_file_id}: {e}")
            await update_status(answer, f"Произошла ошибка во время обработки видео: {str(e)}")
            return None
        finally:
            pass


def process_video_sync(video_file_id: str, video_path: str, answer: Message, loop: asyncio.AbstractEventLoop) -> Optional[str]:
    current_thread = threading.current_thread()
    active_tasks[video_file_id] = current_thread
    
    clip = None
    logo = None
    try:
        asyncio.run_coroutine_threadsafe(
            update_status(answer, "🔄 Разбираем видео на кадры..."), 
            loop
        ).result()
        
        clip = VideoFileClip(video_path, 
                           fps_source='fps',
                           verbose=False,
                           audio=False)
        
        if not clip.reader or clip.reader.lastread is None:
            raise ValueError("Invalid video file - cannot read frames")

        asyncio.run_coroutine_threadsafe(
            update_status(answer, "🔄 Уникализируем каждый кадр..."), 
            loop
        ).result()
        clip = clip.fx(vfx.speedx, 1.02)

        asyncio.run_coroutine_threadsafe(
            update_status(answer, "🔄 Изменяем цветовую гамму..."), 
            loop
        ).result()
        clip = clip.fx(vfx.colorx, 1.25)

        asyncio.run_coroutine_threadsafe(
            update_status(answer, "🔄 Накладываем уникализирующую сетку..."), 
            loop
        ).result()
        logo = ImageClip("videos/1.png")
        logo = logo.set_duration(clip.duration).resize(
            width=clip.size[0], height=clip.size[1]).set_position("center")

        final_clip = CompositeVideoClip([clip, logo])
        output_path = f"videos/processed_{video_file_id}.mp4"
        
        asyncio.run_coroutine_threadsafe(
            update_status(answer, "🔄 Собираем кадры в видео с другим битрейтом..."), 
            loop
        ).result()
        
        asyncio.run_coroutine_threadsafe(
            update_status(answer, "🔄 Чистим метаданные, меняем исходный код видео..."), 
            loop
        ).result()

        final_clip.write_videofile(
            output_path,
            codec='libx264',
            preset='ultrafast',
            bitrate='3000k',
            threads=2,
            audio=False,
            logger='bar'
        )

        return output_path
        
    except Exception as e:
        logging.error(f"Error in process_video_sync: {e}")
        raise
    finally:
        if clip is not None:
            try:
                clip.close()
            except Exception as e:
                logging.error(f"Error closing clip: {e}")
        
        if logo is not None:
            try:
                logo.close()
            except Exception as e:
                logging.error(f"Error closing logo: {e}")
        
        active_tasks.pop(video_file_id, None)


@user_router.message(MediaGroupFilter(), F.video)
@media_group_handler
async def handle_album(messages: List[Message]):
    for message in messages:
        await message.answer("Пожалуйста, отправьте видео одно за другим, а не в альбоме.")
        return


async def cleanup_resources(video_path: str, output_path: Optional[str]):
    try:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
    except Exception as e:
        logging.error(f"Error cleaning up files: {e}")


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
        file = await asyncio.wait_for(
            message.bot.get_file(video_file_id),
            timeout=DOWNLOAD_TIMEOUT
        )
    except asyncio.TimeoutError:
        await message.answer("⚠️ Скачивание файла заняло слишком много времени")
        return
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
    try:
        await asyncio.wait_for(
            message.bot.download(file=file, destination=video_path),
            timeout=DOWNLOAD_TIMEOUT
        )
    except asyncio.TimeoutError:
        await message.answer("⚠️ Скачивание файла заняло слишком много времени")
        async with queue_lock:
            task_queue[:] = [t for t in task_queue if t["file_id"] != video_file_id]
        return

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
    bot_token = message.bot.token
    output_path = None

    try:
        loop = asyncio.get_running_loop()
        output_path = await process_video_async(video_file_id, video_path, answer, loop)

        if output_path:
            try:
                await message.bot.send_video(
                    chat_id=message.chat.id,
                    video=FSInputFile(path=output_path)
                )
                await update_status(answer, "📹 <i>Ваше видео было успешно обработано и отправлено!</i>")
                await message.bot.send_message(
                    chat_id=message.chat.id,
                    text='📹 <i>Пожалуйста, отправьте видео, которое вы хотели бы обработать. '
                         'Размер файла не должен превышать 20 МБ.</i>'
                )
            except Exception as e:
                logging.error(f"Error sending video: {e}")
                await message.answer("Произошла ошибка при отправке видео. Попробуйте позже...")
    except asyncio.TimeoutError:
        pass
    except Exception as e:
        logging.error(f"Error in handle_video_processing: {e}")
        await message.answer("Произошла ошибка при обработке видео. Попробуйте позже...")
    finally:
        try:
            await db.sql_set_user_processing(message.from_user.id, bot_token, False)
            await cleanup_resources(video_path, output_path)
            
            async with queue_lock:
                task_queue[:] = [t for t in task_queue if t["file_id"] != video_file_id]
                logging.info(f"🧹 Задача {video_file_id} удалена из очереди")
                
        except Exception as e:
            logging.error(f"Error in cleanup: {e}")


@user_router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=KICKED))
async def user_blocked_bot(event: ChatMemberUpdated, db):
    bot_token = event.bot.token
    await db.sql_update_user_status(is_active=False, user_id=event.from_user.id, bot_token=bot_token)


@user_router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=MEMBER))
async def user_unblocked_bot(event: ChatMemberUpdated, db):
    bot_token = event.bot.token
    await db.sql_update_user_status(is_active=True, user_id=event.from_user.id, bot_token=bot_token)


async def monitor_tasks():
    while True:
        await asyncio.sleep(60)
        now = time.time()
        async with queue_lock:
            for task in task_queue[:]:
                if "start_time" in task and (now - task["start_time"]) > PROCESSING_TIMEOUT * 2:
                    logging.warning(f"Удаляем зависшую задачу {task['file_id']}")
                    cancel_stuck_task(task["file_id"])
                    task_queue.remove(task)


async def on_startup():
    asyncio.create_task(monitor_tasks())