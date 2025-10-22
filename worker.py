# Создать файл worker.py:
import asyncio
import logging
import os
from aiogram import Bot
from dotenv import load_dotenv
from db import redis_client
import json
from datetime import datetime
from tasks import check_expired_posts

load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)

async def process_task_queue():
    """Обработчик очереди задач"""
    while True:
        try:
            # Получаем задачу из очереди
            task_data = await redis_client.blpop("task_queue", timeout=1)
            if task_data:
                _, task_json = task_data
                task = json.loads(task_json)
                
                task_type = task.get("type")
                if task_type == "check_expired":
                    # Запускаем проверку просроченных постов
                    await check_expired_posts(bot)
                # Здесь можно добавить другие типы задач
                
        except Exception as e:
            logging.error(f"Ошибка при обработке задачи: {e}")
            await asyncio.sleep(5)

async def main():
    """Основная функция воркера"""
    logging.info("Запуск воркера для обработки задач...")
    await process_task_queue()

if __name__ == "__main__":
    asyncio.run(main())

# В bot.py добавить планировщик задач:
async def schedule_tasks():
    """Планировщик задач"""
    while True:
        try:
            # Добавляем задачу проверки просроченных постов в очередь
            task = {
                "type": "check_expired",
                "created_at": datetime.now().isoformat()
            }
            await redis_client.rpush("task_queue", json.dumps(task))
            logging.info("Задача проверки просроченных постов добавлена в очередь")
            
            # Ждем 12 часов перед следующим планированием
            await asyncio.sleep(12*60*60)
        except Exception as e:
            logging.error(f"Ошибка при планировании задач: {e}")
            await asyncio.sleep(5*60)

# В функции main() в bot.py добавить:
asyncio.create_task(schedule_tasks())
