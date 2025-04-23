import random
from typing import Optional

from discord import Member
from discord.ext import commands
from loguru import logger

from iqbot import db


class IQ(commands.Cog):
    bot: commands.Bot

    def __init__(self, bot):
        self.bot = bot

    def iq_comment(self, iq: int) -> str:
        if iq < 0:
            return random.choice(
                [
                    f"{iq} IQ? That's not an IQ, that's a cry for help.",
                    f"{iq} IQ? You're operating at a cognitive overdraft.",
                    f"{iq} IQ? Congratulations, you've looped back around and invented anti-thought.",
                    f"{iq} IQ? That's less IQ and more like an intellectual black hole.",
                    f"{iq} IQ? Negative IQ? Are you thinking *in reverse*?",
                    f"{iq} IQ? Your brain waves are being sued for defamation by static.",
                    f"{iq} IQ? You're so unintelligent, reality itself is confused.",
                    f"{iq} IQ? You may have discovered the theoretical limit of dumb.",
                ]
            )
        elif iq < 50:
            return f"{iq} IQ? You might be legally required to wear a helmet to use a keyboard."
        elif iq < 70:
            return f"{iq} IQ? Ah, the intellectual horsepower of a garden gnome."
        elif iq < 90:
            return (
                f"{iq} IQ? Room temperature in Fahrenheit. Respectable. For a potato."
            )
        elif iq < 100:
            return f"{iq} IQ? The lights are on, but they're flickering."
        elif iq < 110:
            return f"{iq} IQ? Decent! Not a genius, but you can probably operate a microwave without supervision."
        elif iq < 130:
            return f"{iq} IQ? You'd win pub quizzes, but probably still get scammed by an email prince."
        elif iq < 150:
            return (
                f"{iq} IQ? Impressive. Do you use that brain for good, or just memes?"
            )
        elif iq < 200:
            return f"{iq} IQ? You're not thinking outside the box. You've **invented** the box."
        elif iq < 500:
            return f"{iq} IQ? I assume you're communicating with me via quantum entanglement."
        elif iq < 1000:
            return (
                f"{iq} IQ? At this point you're basically a minor Lovecraftian deity."
            )
        else:
            return random.choice(
                [
                    f"{iq} IQ? That's not IQ. That's just raw cosmic hubris.",
                    f"{iq} IQ? Congratulations, you've ascended beyond comprehension. Please don't vaporize us.",
                    f"{iq} IQ? Even GPT is feeling insecure now.",
                    f"{iq} IQ? Legend says your thoughts cause gravitational lensing.",
                ]
            )

    @commands.slash_command(name="iq", description="checks bot latency")
    async def ping(self, ctx, member: Optional[Member] = None):
        try:
            if member is None:
                member = ctx.author

            assert member is not None
            user = await db.read_or_add_user(ctx.guild.id, member.id)
            logger.info(f"Retrieved user: {user}")

            if user.iq is None:
                await ctx.respond(f"Error: {user.display_name} has no IQ set.")
            else:
                await ctx.respond(f"{member.mention} {self.iq_comment(user.iq)}")
        except Exception as e:
            logger.error(f"Error in ping command: {e}")

    @commands.slash_command(name="top", description="checks bot latency")
    async def top(self, ctx):
        try:
            top_users, bottom_users = await db.read_head_tail_iqs(ctx.guild.id, 5)
            message = "## Top IQs\n"
            for user in top_users:
                member = await ctx.guild.fetch_member(user.user_id)
                if member is None:
                    raise ValueError("Member not found")
                else:
                    message += f"- {member.display_name}: {user.iq} IQ\n"
            if len(bottom_users) > 0:
                message += "\n## Bottom IQs\n"
                for user in bottom_users:
                    member = await ctx.guild.fetch_member(user.user_id)
                    if member is None:
                        raise ValueError("Member not found")
                    else:
                        message += f"- {member.display_name}: {user.iq} IQ\n"
            await ctx.respond(message)
        except Exception as e:
            logger.error(f"Error in top command: {e}")
            await ctx.respond("Error retrieving IQ data.")


def setup(bot):
    bot.add_cog(IQ(bot))
