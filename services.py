from sqlalchemy import select
from db import async_session, Draft

async def get_draft(user_id: int):
    async with async_session() as session:
        result = await session.execute(select(Draft).where(Draft.user_id == user_id))
        return result.scalar_one_or_none()

async def create_or_update_draft(user_id: int, **kwargs):
    async with async_session() as session:
        result = await session.execute(select(Draft).where(Draft.user_id == user_id))
        draft = result.scalar_one_or_none()
        if not draft:
            draft = Draft(user_id=user_id, **kwargs)
            session.add(draft)
        else:
            for key, value in kwargs.items():
                setattr(draft, key, value)
        await session.commit()
        return draft

async def delete_draft(user_id: int):
    async with async_session() as session:
        result = await session.execute(select(Draft).where(Draft.user_id == user_id))
        draft = result.scalar_one_or_none()
        if draft:
            await session.delete(draft)
            await session.commit()
