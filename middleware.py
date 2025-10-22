import asyncio
import time
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

class AntiSpamMiddleware(BaseMiddleware):
    def __init__(self, min_interval: float = 1.0, max_violations: int = 3, ban_time: int = 10):
        self.min_interval = min_interval       # Минимальный интервал между нажатиями
        self.max_violations = max_violations   # Сколько раз можно "спамить" до блокировки
        self.ban_time = ban_time               # Время блокировки в секундах

        self._last_action_time = {}   # {user_id: timestamp}
        self._violations = {}         # {user_id: кол-во нарушений}
        self._banned_until = {}       # {user_id: timestamp до какого момента забанен}

    async def __call__(self, handler, event, data):
        user_id = None

        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if user_id is None:
            return await handler(event, data)

        now = time.monotonic()

        # Проверяем, не забанен ли пользователь
        banned_until = self._banned_until.get(user_id, 0)
        if now < banned_until:
            remaining = int(banned_until - now)
            if isinstance(event, CallbackQuery):
                await event.answer(f"🚫 Подожди {remaining} с.", show_alert=False)
            elif isinstance(event, Message):
                await event.answer(f"🚫 Ты слишком часто пишешь! Подожди {remaining} секунд.")
            return

        # Проверяем частоту
        last_time = self._last_action_time.get(user_id, 0)
        if now - last_time < self.min_interval:
            # Засчитываем нарушение
            self._violations[user_id] = self._violations.get(user_id, 0) + 1

            # Если превышено количество нарушений — баним
            if self._violations[user_id] >= self.max_violations:
                self._banned_until[user_id] = now + self.ban_time
                self._violations[user_id] = 0
                if isinstance(event, CallbackQuery):
                    await event.answer(f"⛔ Слишком часто! Блокировка на {self.ban_time} секунд.", show_alert=True)
                elif isinstance(event, Message):
                    await event.answer(f"⛔ Ты слишком активен! Заблокирован на {self.ban_time} секунд.")
                return

            # Просто предупреждение
            if isinstance(event, CallbackQuery):
                await event.answer("⏳ Не так быстро!", show_alert=False)
            elif isinstance(event, Message):
                await event.answer("⏳ Не так быстро!")
            return

        # Всё ок — обновляем время последнего действия и обнуляем нарушения
        self._last_action_time[user_id] = now
        self._violations[user_id] = 0

        return await handler(event, data)
