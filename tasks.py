# В tasks.py заменить функцию check_expired_posts:
from telegram_utils import safe_delete_message
from db import async_session, User, Draft
from sqlalchemy import update
from db import redis_client
from datetime import datetime, timedelta, timezone
import logging
import asyncio
from dotenv import load_dotenv
import os
from sqlalchemy import select

load_dotenv()
CHAT_ID = int(os.getenv("CHAT_ID"))

async def check_expired_posts(bot):
    while True:
        try:
            async with async_session() as session:
                # Получаем все просроченные черновики
                now = datetime.now(timezone.utc)
                result = await session.execute(
                    select(Draft).where(
                        Draft.is_draft == False,
                        Draft.published_at != None,
                        Draft.published_at + timedelta(days=30) <= now
                    )
                )
                expired_drafts = result.scalars().all()
                
                # Собираем ID для bulk-update
                expired_ids = [draft.id for draft in expired_drafts]
                
                if expired_ids:
                    # Выполняем bulk-update
                    await session.execute(
                        update(Draft)
                        .where(Draft.id.in_(expired_ids))
                        .values(is_draft=True, paid=False, published_at=None)
                    )
                    await session.commit()
                    
                    # Удаляем сообщения с ограничением скорости
                    for draft in expired_drafts:
                        if draft.message_id:
                            await safe_delete_message(bot, CHAT_ID, draft.message_id)
                            if draft.theme_message_id:
                                await safe_delete_message(bot, CHAT_ID, draft.theme_message_id)
                            # Ограничиваем скорость удаления (не более 20 сообщений в секунду)
                            await asyncio.sleep(0.05)
                        
                        logging.info(f"Резюме пользователя {draft.user_id} возвращено в черновик")
                        
                        # Инвалидируем кеш для этого пользователя
                        user_result = await session.execute(
                            select(User.telegram_id).where(User.id == draft.user_id)
                        )
                        telegram_id = user_result.scalar_one_or_none()
                        if telegram_id:
                            cache_key = f"draft:{telegram_id}"
                            await redis_client.delete(cache_key)
                
            # Проверяем каждые 12 часов
            await asyncio.sleep(12*60*60)
        except Exception as e:
            logging.error(f"Ошибка при проверке просроченных постов: {e}")
            # В случае ошибки ждем 5 минут и пробуем снова
            await asyncio.sleep(5*60)