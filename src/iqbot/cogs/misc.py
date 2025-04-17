# type: ignore

import random

from discord.ext import commands
from discord.ext.commands import Context
from loguru import logger
from senor_bot.checks import bot_manager


class Misc(commands.Cog):
    bot: commands.Bot

    def __init__(self, bot):
        self.bot = bot

    @commands.check(bot_manager)
    @commands.slash_command(name="ping", description="checks bot latency")
    async def ping(self, ctx: commands.Context):
        try:
            await ctx.respond(f"Pong! ```latency = {round(self.bot.latency, 1)}ms```")
        except Exception as e:
            logger.error(f"Error in ping command: {e}")


def setup(bot):
    bot.add_cog(Misc(bot))
