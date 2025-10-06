import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from db import init_db
from handlers import register_handlers
from tasks import check_expired_posts

load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


async def main():
    await init_db()
    register_handlers(dp)
    asyncio.create_task(check_expired_posts(bot))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
