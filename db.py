import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, BigInteger, Text, DateTime, func, Boolean

DATABASE_URL = "postgresql+asyncpg://postgres:Sasha2010@localhost/botfrilance"

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class Draft(Base):
    __tablename__ = "drafts"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, nullable=False, unique=True)
    photo = Column(Text)
    description = Column(Text)
    contact = Column(Text)
    message_id = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    published_at = Column(DateTime(timezone=True))
    paid = Column(Boolean, default=False)
    payment_id = Column(Text)
    is_draft = Column(Boolean, default=True)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    asyncio.run(init_db())
    print("База данных и таблицы созданы!")
