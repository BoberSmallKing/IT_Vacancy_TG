from sqlalchemy import select, delete
from db import async_session, Draft, User
from datetime import datetime, timezone
import hashlib
import json
from db import redis_client

def calculate_draft_hash(draft):
    """Создает хеш из основных полей черновика для отслеживания изменений"""
    data = {
        "description": draft.description,
        "contact": draft.contact,
        "theme_name": draft.theme_name,
        "photo": bool(draft.photo)  # Только факт наличия фото
    }
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()

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
    """Возвращает черновик по telegram_id пользователя с использованием кеша Redis"""
    # Проверяем кеш
    cache_key = f"draft:{telegram_id}"
    cached_data = await redis_client.get(cache_key)
    
    if cached_data:
        # Если данные в кеше, десериализуем и возвращаем
        draft_dict = json.loads(cached_data)
        # Конвертируем даты из ISO-строк обратно в datetime
        for key in ("created_at", "published_at"):
            value = draft_dict.get(key)
            if isinstance(value, str):
                try:
                    draft_dict[key] = datetime.fromisoformat(value)
                except Exception:
                    draft_dict[key] = None
        # Создаем объект Draft из словаря
        draft = Draft()
        for key, value in draft_dict.items():
            setattr(draft, key, value)
        return draft
    
    # Если нет в кеше, получаем из БД
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
        draft = draft_result.scalar_one_or_none()
        
        if draft:
            # Сохраняем в кеш на 5 минут
            draft_dict = {c.name: getattr(draft, c.name) for c in draft.__table__.columns}
            # Преобразуем datetime в строки
            for key, value in draft_dict.items():
                if isinstance(value, datetime):
                    draft_dict[key] = value.isoformat()
            
            await redis_client.setex(cache_key, 300, json.dumps(draft_dict))
        
        return draft

async def create_or_update_draft(telegram_id: int, **kwargs):
    """Создаёт или обновляет черновик пользователя по telegram_id с использованием кеша Redis"""
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
        
        # Вычисляем хеш для отслеживания изменений
        draft.last_hash = calculate_draft_hash(draft)

        await session.commit()
        await session.refresh(draft)
        
        # Инвалидируем кеш
        cache_key = f"draft:{telegram_id}"
        await redis_client.delete(cache_key)
        
        return draft

async def delete_draft(telegram_id: int):
    """Удаляет черновик по telegram_id и инвалидирует кеш"""
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
        
        # Инвалидируем кеш
        cache_key = f"draft:{telegram_id}"
        await redis_client.delete(cache_key)


