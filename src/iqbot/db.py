import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime
from functools import wraps
from pprint import pformat
from typing import Optional, Sequence

from loguru import logger
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import Mapped, declarative_base, mapped_column

from iqbot.config import settings

Base = declarative_base()

engine = create_async_engine(
    settings.database.url,
    echo=settings.database.echo,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
    pool_recycle=settings.database.pool_recycle,
    pool_timeout=settings.database.pool_timeout,
)

async_session = async_sessionmaker(engine, expire_on_commit=False)


class User(Base):
    __tablename__ = "users"
    __allow_unmapped__ = True

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(index=True)
    user_id: Mapped[int] = mapped_column(index=True)
    iq: Mapped[Optional[int]] = mapped_column(default=100)

    def __repr__(self):
        return pformat(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "user_id": self.user_id,
            "iq": self.iq,
        }


class Bet(Base):
    __tablename__ = "bets"
    __allow_unmapped__ = True

    message_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(default=lambda: datetime.now())
    user_id_1: Mapped[int] = mapped_column(index=True)
    user_id_2: Mapped[int] = mapped_column(index=True)
    bet: Mapped[int]
    is_open: Mapped[bool] = mapped_column(default=True)
    winner: Mapped[Optional[int]] = mapped_column(nullable=True)

    def __repr__(self):
        return pformat(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "user_id_1": self.user_id_1,
            "user_id_2": self.user_id_2,
            "bet": self.bet,
            "is_open": self.is_open,
            "winner": self.winner,
        }


def db_logger(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            logger.info(f"{func.__name__} executed in {elapsed_time:.2f} seconds")
            return result
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            return None

    return wrapper


@asynccontextmanager
async def get_session():
    async with async_session() as session:
        async with session.begin():
            yield session


@db_logger
async def add_user(user: User) -> None:
    async with get_session() as session:
        session.add(user)
        await session.commit()


@db_logger
async def read_user(guild_id: int, user_id: int) -> Optional[User]:
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.guild_id == guild_id, User.user_id == user_id)
        )
        return result.scalar_one_or_none()


@db_logger
async def read_or_add_user(guild_id: int, user_id: int) -> User:
    user = await read_user(guild_id, user_id)
    if user is None:
        user = User(guild_id=guild_id, user_id=user_id, iq=100)
        await add_user(user)
        logger.info(f"New user created: {user}")
    else:
        logger.info(f"Existing user found: {user}")
    return user


@db_logger
async def read_or_add_users(guild_id: int, user_ids: list[int]) -> list[User]:
    async with get_session() as session:
        stmt = select(User).where(User.guild_id == guild_id, User.user_id.in_(user_ids))
        result = await session.execute(stmt)
        existing_users = {user.user_id: user for user in result.scalars().all()}

        missing_user_ids = set(user_ids) - existing_users.keys()
        new_users = [
            User(guild_id=guild_id, user_id=user_id, iq=100)
            for user_id in missing_user_ids
        ]

        session.add_all(new_users)
        await session.commit()
        return list(existing_users.values()) + new_users


@db_logger
async def upsert_user_iq(guild_id: int, user_id: int, iq: int) -> User:
    async with get_session() as session:
        stmt = select(User).where(User.user_id == user_id, User.guild_id == guild_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            user.iq = iq
        else:
            user = User(user_id=user_id, guild_id=guild_id, iq=iq)
            session.add(user)

        await session.commit()
    return user


@db_logger
async def remove_user(guild_id: int, user_id: int) -> None:
    async with get_session() as session:
        stmt = select(User).where(User.user_id == user_id, User.guild_id == guild_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            await session.delete(user)
            await session.commit()
            logger.info(f"User {user} removed from the database")
        else:
            logger.warning(f"User {user_id} not found in the database")


@db_logger
async def add_bet(bet: Bet) -> None:
    async with get_session() as session:
        session.add(bet)
        await session.commit()


@db_logger
async def read_user_bets(user_id: int) -> Sequence[Bet]:
    async with get_session() as session:
        stmt = select(Bet).where(
            (Bet.user_id_1 == user_id) | (Bet.user_id_2 == user_id)  # type: ignore
        )
        result = await session.execute(stmt)
        bets = result.scalars().all()
    return bets


@db_logger
async def read_bet(message_id) -> Optional[Bet]:
    async with get_session() as session:
        stmt = select(Bet).where(Bet.message_id == message_id)
        result = await session.execute(stmt)
        bet = result.scalar_one_or_none()
    return bet


async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(async_main())
