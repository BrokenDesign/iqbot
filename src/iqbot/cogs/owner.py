from discord import Member
from discord.ext import commands
from discord.ext.commands import Context
from loguru import logger

from iqbot import db, gpt
from iqbot.checks import bot_manager


class Owner(commands.Cog):
    bot: commands.Bot

    def __init__(self, bot):
        self.bot = bot

    @commands.check(bot_manager)
    @commands.slash_command(name="add", description="adds user to the IQ database")
    async def add(self, ctx, member: Member):
        try:
            await db.upsert_user_iq(ctx.guild.id, member.id, 100)
            await ctx.respond(f"Added {member.name} to the IQ database")
        except Exception as e:
            logger.error(f"Error in add command: {e}")
            await ctx.respond(f"Failed to add {member.name} to the IQ database")

    @commands.check(bot_manager)
    @commands.slash_command(name="set", description="updates user IQ")
    async def set(self, ctx, member: Member, iq: int):
        try:
            await db.upsert_user_iq(ctx.guild.id, member.id, iq)
            await ctx.respond(f"Set {member.name}'s IQ to {iq}")
        except Exception as e:
            logger.error(f"Error in set command: {e}")
            await ctx.respond(f"Failed to set {member.name}'s IQ")

    @commands.check(bot_manager)
    @commands.slash_command(
        name="remove", description="removes user from the IQ database"
    )
    async def remove(self, ctx, member: Member):
        try:
            await db.remove_user(ctx.guild.id, member.id)
            await ctx.respond(f"Removed {member.name} from the IQ database")
        except Exception as e:
            logger.error(f"Error in remove command: {e}")
            await ctx.respond(f"Failed to remove {member.name} from the IQ database")

    @commands.check(bot_manager)
    @commands.slash_command(name="question", description="resets user IQ to 100")
    async def question(self, ctx, question: str):
        try:
            response = await gpt.send_prompt(ctx, question)
            ctx.respond(response)
        except Exception as e:
            logger.error(f"Error in question command: {e}")
            await ctx.respond("Failed to get a response from GPT")


def setup(bot):
    bot.add_cog(Owner(bot))
