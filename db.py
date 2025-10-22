# db.py
import asyncio
import os
import secrets
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy import Column, Integer, BigInteger, Text, DateTime, func, Boolean, ForeignKey, UniqueConstraint
from dotenv import load_dotenv
import redis.asyncio as redis

load_dotenv()

REDIS_URL = f"redis://{os.getenv('REDIS_HOST')}:{os.getenv('REDIS_PORT')}/0"
redis_pool = redis.ConnectionPool.from_url(REDIS_URL)
redis_client = redis.Redis.from_pool(redis_pool)

# Настройка пула подключений к базе данных
DATABASE_URL = f"postgresql+asyncpg://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
engine = create_async_engine(
    DATABASE_URL, 
    echo=False,
    pool_size=20,
    max_overflow=40,
    pool_recycle=1800,  
    pool_timeout=10      
)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


# === Пользователь ===
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(Text)
    id_key = Column(Text, unique=True, nullable=False, default=lambda: secrets.token_hex(8))
    rating = Column(Integer, default=0)
    last_key_update = Column(DateTime(timezone=True), default=func.now())
    is_first_visit = Column(Boolean, default=True)

    drafts = relationship("Draft", back_populates="user", cascade="all, delete-orphan")
    

    def update_id_key(self):
        self.id_key = secrets.token_hex(8)
        self.last_key_update = datetime.now()


# === Черновик ===
class Draft(Base):
    __tablename__ = "drafts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    photo = Column(Text)
    description = Column(Text)
    contact = Column(Text)
    message_id = Column(Integer)
    theme_message_id = Column(Integer)
    theme_name = Column(Text)
    theme_change_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    published_at = Column(DateTime(timezone=True))
    paid = Column(Boolean, default=False)
    payment_id = Column(Text)
    is_draft = Column(Boolean, default=True)
    last_hash = Column(Text)

    user = relationship("User", back_populates="drafts")
    

class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True)
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)    
    score = Column(Integer, nullable=False) 
    created_at = Column(DateTime(timezone=True), server_default=func.now())


    __table_args__ = (UniqueConstraint("from_user_id", "to_user_id", name="unique_rating"),)


    from_user = relationship("User", foreign_keys=[from_user_id], backref="given_ratings")
    to_user = relationship("User", foreign_keys=[to_user_id], backref="received_ratings")


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    asyncio.run(init_db())
    print("База данных и таблицы созданы!")
