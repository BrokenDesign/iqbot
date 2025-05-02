from discord import ApplicationContext, Member, SlashCommandGroup
from discord.ext import commands
from loguru import logger

from iqbot import db
from iqbot.checks import bot_manager


class Admin(commands.Cog):
    bot: commands.Bot

    def __init__(self, bot):
        self.bot = bot

    admin = SlashCommandGroup("admin", "Admin only commands")

    @admin.command(name="add", description="Adds user to the IQ database")
    @commands.check(bot_manager)
    async def add(self, ctx: ApplicationContext, member: Member):
        try:
            await db.upsert_user_iq(ctx.guild.id, member.id, 100)
            await ctx.respond(f"Added {member.name} to database with IQ 100")
        except Exception as e:
            logger.error(f"Error in add command: {e}")
            await ctx.respond(f"Failed to add {member.name}")

    @admin.command(name="set", description="Updates user IQ")
    @commands.check(bot_manager)
    async def set(self, ctx: ApplicationContext, member: Member, iq: int):
        try:
            await db.upsert_user_iq(ctx.guild.id, member.id, iq)
            await ctx.respond(f"Set {member.name}'s IQ to {iq}")
        except Exception as e:
            logger.error(f"Error in set command: {e}")
            await ctx.respond(f"Failed to set {member.name}'s IQ")

    @admin.command(name="remove", description="Remove user from the database")
    @commands.check(bot_manager)
    async def remove(self, ctx: ApplicationContext, member: Member):
        try:
            user = await db.read_user(ctx.guild.id, member.id)
            if user is None:
                await ctx.respond(f"{member.name} is not found.")
                return
            await db.remove_user(ctx.guild.id, member.id)
            await ctx.respond(f"Removed {member.name} from the IQ database")
        except Exception as e:
            logger.error(f"Error in remove command: {e}")
            await ctx.respond(f"Failed to remove {member.name} from the IQ database")


def setup(bot):
    bot.add_cog(Admin(bot))
