import random

from discord.ext import commands
from loguru import logger


class Misc(commands.Cog):
    bot: commands.Bot

    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="ping", description="checks bot latency")
    async def ping(self, ctx):
        try:
            await ctx.respond(f"Pong! ```latency = {round(self.bot.latency, 1)}ms```")
        except Exception as e:
            logger.error(f"Error in ping command: {e}")

    @commands.slash_command(name="topic", description="sends a debate topic")
    async def topic(self, ctx):
        with open("resources/debate_topics.txt", "r") as f:
            topics = f.readlines()
            await ctx.respond(random.choice(topics).strip())


def setup(bot):
    bot.add_cog(Misc(bot))
