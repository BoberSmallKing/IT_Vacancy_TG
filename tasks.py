import asyncio
import os
from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy import select
from db import async_session, Draft
from dotenv import load_dotenv

load_dotenv()

CHAT_ID = os.getenv("CHAT_ID")

async def check_expired_posts(bot):
    while True:
        async with async_session() as session:
            result = await session.execute(
                select(Draft).where(Draft.is_draft == False, Draft.published_at != None)
            )
            drafts = result.scalars().all()
            for draft in drafts:
                expiry = draft.published_at + timedelta(days=30)
                remaining = expiry - datetime.now(timezone.utc)
                if remaining.total_seconds() <= 0:
                    draft.is_draft = True
                    draft.paid = False
                    draft.published_at = None
                    if draft.message_id:
                        try:
                            await bot.delete_message(chat_id=CHAT_ID, message_id=draft.message_id)
                        except Exception as e:
                            logging.error(f"Не удалось удалить сообщение: {e}")
                    await session.commit()
                    logging.info(f"Резюме пользователя {draft.user_id} возвращено в черновик")
        await asyncio.sleep(12*60*60) 