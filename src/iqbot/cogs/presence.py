from discord import Member
from discord.ext import commands
from loguru import logger
from sqlalchemy import select

from iqbot.db import User, db_logger, get_session


class Presence(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    @db_logger
    async def on_member_join(self, member: Member):
        logger.info(f"Member joined: {member.name} ({member.id})")
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.member_id == member.id)
            )
            user = result.scalar_one_or_none()
            if user:
                user.is_present = True
                await session.commit()

    @commands.Cog.listener()
    @db_logger
    async def on_member_remove(self, member: Member):
        logger.info(f"Member left: {member.name} ({member.id})")
        async with get_session() as session:
            result = await session.execute(
                select(User).where(User.member_id == member.id)
            )
            user = result.scalar_one_or_none()
            if user:
                user.is_present = False
                await session.commit()


def setup(bot):
    bot.add_cog(Presence(bot))
