# Создать файл telegram_utils.py:
import asyncio
import logging
import time
from typing import Any, Optional, Union
from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup


telegram_semaphore = asyncio.Semaphore(20)  

last_calls = []
async def rate_limit(max_per_second=30):
    global last_calls
    now = time.time()
    # Удаляем старые вызовы (старше 1 секунды)
    last_calls = [t for t in last_calls if now - t < 1]
    if len(last_calls) >= max_per_second:
        # Подождать, если слишком много запросов
        sleep_time = 1 - (now - last_calls[0])
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)
    last_calls.append(time.time())

async def safe_send(
    bot: Bot,
    chat_id: Union[int, str],
    text: str,
    parse_mode: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    message_thread_id: Optional[int] = None,
    **kwargs
) -> Optional[Message]:
    """Безопасная отправка сообщений с использованием семафора"""
    async with telegram_semaphore:
        await rate_limit()
        try:
            return await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                message_thread_id=message_thread_id,
                **kwargs
            )
        except Exception as e:
            logging.error(f"Ошибка при отправке сообщения: {e}")
            return None

async def safe_send_photo(
    bot: Bot,
    chat_id: Union[int, str],
    photo: Union[str, Any],
    caption: Optional[str] = None,
    parse_mode: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    message_thread_id: Optional[int] = None,
    **kwargs
) -> Optional[Message]:
    """Безопасная отправка фото с использованием семафора"""
    async with telegram_semaphore:
        try:
            return await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                message_thread_id=message_thread_id,
                **kwargs
            )
        except Exception as e:
            logging.error(f"Ошибка при отправке фото: {e}")
            return None

async def safe_delete_message(
    bot: Bot,
    chat_id: Union[int, str],
    message_id: int
) -> bool:
    """Безопасное удаление сообщения с использованием семафора"""
    async with telegram_semaphore:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            return True
        except Exception as e:
            logging.error(f"Ошибка при удалении сообщения: {e}")
            return False