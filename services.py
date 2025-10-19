from sqlalchemy import select, delete
from db import async_session, Draft, User
from datetime import datetime, timezone


# --- Пользователь ---
async def get_user(telegram_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def register_user(telegram_id: int, username: str | None = None):
    """Создаёт пользователя, если его нет"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(telegram_id=telegram_id, username=username)
            session.add(user)
            await session.commit()
            await session.refresh(user)  # получаем user.id
        return user


async def refresh_id_key(user: User):
    """Обновляем ключ, если прошла неделя"""
    if not user.last_key_update or (datetime.now(timezone.utc) - user.last_key_update).days >= 7:
        user.update_id_key()
        async with async_session() as session:
            session.add(user)
            await session.commit()


# --- Черновики ---
async def get_draft(telegram_id: int):
    """Возвращает черновик по telegram_id пользователя"""
    async with async_session() as session:
        # Получаем внутренний ID пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return None

        draft_result = await session.execute(
            select(Draft).where(Draft.user_id == user.id)
        )
        return draft_result.scalar_one_or_none()

async def create_or_update_draft(telegram_id: int, **kwargs):
    """
    Создаёт или обновляет черновик пользователя по telegram_id.
    Работает безопасно, не перезаписывает None, поддерживает частичное обновление.
    """
    async with async_session() as session:
        # --- Находим пользователя ---
        result = await session.execute(
            select(User.id).where(User.telegram_id == telegram_id)
        )
        user_id = result.scalar_one_or_none()
        if not user_id:
            return None

        # --- Находим или создаём черновик ---
        result = await session.execute(
            select(Draft).where(Draft.user_id == user_id)
        )
        draft = result.scalar_one_or_none()

        if not draft:
            draft = Draft(user_id=user_id)
            session.add(draft)

        # --- Обновляем только переданные значения ---
        for key, value in kwargs.items():
            # чтобы не затирать поля None-ами по ошибке
            if value is not None and hasattr(draft, key):
                setattr(draft, key, value)

        await session.commit()
        await session.refresh(draft)
        return draft


async def delete_draft(telegram_id: int):
    """Удаляет черновик по telegram_id"""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return

        await session.execute(
            delete(Draft).where(Draft.user_id == user.id)
        )
        await session.commit()


