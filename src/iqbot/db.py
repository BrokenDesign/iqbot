# type: ignore

import asyncio
from pprint import pformat
from typing import Optional

from loguru import logger
from sqlalchemy import Column, Integer
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import declarative_base

from iqbot.config import settings

Base = declarative_base()
engine = create_async_engine(settings.database.url, echo=False, pool_recycle=3600)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class User(Base):
    __tablename__ = "iqs"
    __allow_unmapped__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(Integer)
    user_id = Column(Integer)
    iq = Column(Integer)

    def __init__(self, guild_id, user_id, iq: Optional[int] = 100) -> None:
        self.guild_id = guild_id
        self.user_id = user_id
        self.iq = iq

    def __repr__(self):
        return pformat(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guild_id": self.guild_id,
            "user_id": self.user_id,
            "iq": self.iq,
        }


async def add_user(user: User) -> None:
    try:
        async with async_session() as session:
            async with session.begin():
                session.add(user)
                await session.commit()
        logger.info(f"User added to database: {user}")
    except Exception as e:
        logger.error(f"Error adding user to database: {e}")


async def read_user(guild_id: int, user_id: int) -> User | None:
    try:
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.guild_id == guild_id, User.user_id == user_id)
            )
            user = result.scalar_one_or_none()
        if user:
            logger.info(f"User read from database: {user}")
            return user
    except Exception as e:
        logger.error(f"Error reading user from database: {e}")
    return None


async def read_or_add_user(guild_id: int, user_id: int) -> User:
    user = await read_user(guild_id, user_id)
    if user is None:
        user = User(guild_id=guild_id, user_id=user_id, iq=100)
        await add_user(user)
    return user


async def read_or_add_users(guild_id: int, user_ids: list[int]) -> list[User]:
    users = []
    for user_id in user_ids:
        user = await read_or_add_user(guild_id, user_id)
        users.append(user)
    return users


async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(async_main())
