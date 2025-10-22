import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
from aiogram.fsm.storage.redis import RedisStorage
from db import REDIS_URL


from dotenv import load_dotenv


from db import init_db
from handlers import register_handlers
from tasks import check_expired_posts
from middleware import AntiSpamMiddleware

load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

storage = RedisStorage.from_url(REDIS_URL)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
anti_spam = AntiSpamMiddleware(min_interval=1.0, max_violations=3, ban_time=10)

dp.message.middleware(anti_spam)
dp.callback_query.middleware(anti_spam)

async def main():
    await init_db()
    register_handlers(dp)
    asyncio.create_task(check_expired_posts(bot))
    await dp.start_polling(bot)

try:
    if __name__ == "__main__":
        asyncio.run(main())
except KeyboardInterrupt:
    print("Бот остоновлен")
