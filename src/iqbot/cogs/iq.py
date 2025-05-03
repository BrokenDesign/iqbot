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
        if iq < 50:
            return random.choice(
                [
                    f"{iq} IQ? You're legally required to have adult supervision online.",
                    f"{iq} IQ? That's not an IQ, that's a body temperature.",
                    f"{iq} IQ? Your neurons are on strike.",
                ]
            )
        elif iq < 70:
            return random.choice(
                [
                    f"{iq} IQ? Impressive—for a garden gnome.",
                    f"{iq} IQ? You're running on potato logic.",
                    f"{iq} IQ? Somehow both underclocked and overheating.",
                ]
            )
        elif iq < 85:
            return random.choice(
                [
                    f"{iq} IQ? Room temperature in Fahrenheit. Ambitious!",
                    f"{iq} IQ? If common sense were currency, you'd be in debt.",
                    f"{iq} IQ? Not dumb, just *retro* thinking.",
                ]
            )
        elif iq < 100:
            return random.choice(
                [
                    f"{iq} IQ? Average—like lukewarm tea and grey wallpaper.",
                    f"{iq} IQ? You're the human equivalent of buffering.",
                    f"{iq} IQ? Mid. In every possible way.",
                ]
            )
        elif iq < 115:
            return random.choice(
                [
                    f"{iq} IQ? Respectable! You'd survive in a cyberpunk dystopia.",
                    f"{iq} IQ? Smart enough to argue online, not smart enough to stop.",
                    f"{iq} IQ? Competent! Just don’t try to rewire the toaster.",
                ]
            )
        elif iq < 130:
            return random.choice(
                [
                    f"{iq} IQ? Pub quiz royalty. Google fears you.",
                    f"{iq} IQ? You're the reason the curve gets curved.",
                    f"{iq} IQ? Sharp. Dangerous if pointed at the wrong topic.",
                ]
            )
        elif iq < 145:
            return random.choice(
                [
                    f"{iq} IQ? Genius-tier. You probably have strong opinions about fonts.",
                    f"{iq} IQ? Smarter than you act online, that's for sure.",
                    f"{iq} IQ? High-functioning sarcasm generator.",
                ]
            )
        elif iq < 160:
            return random.choice(
                [
                    f"{iq} IQ? Borderline superhuman. Do you even experience loading times?",
                    f"{iq} IQ? Ideas per minute: lethal.",
                    f"{iq} IQ? You might be writing this simulation.",
                ]
            )
        else:
            return random.choice(
                [
                    f"{iq} IQ? Honestly, that’s terrifying.",
                    f"{iq} IQ? If you're not an alien, you're at least on contract.",
                    f"{iq} IQ? Go touch grass — for science.",
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

    @commands.slash_command(name="top", description="Outputs top and bottom IQs")
    async def top(self, ctx):
        await ctx.defer()
        try:
            top_users = {}
            bottom_users = {}

            async with db.get_session() as session:
                async for user in db.read_top_iqs(ctx.guild.id):
                    try:
                        member = await ctx.guild.fetch_member(user.user_id)
                    except:
                        member = None

                    if member:
                        top_users[member.id] = (member.display_name, user.iq)
                    else:
                        await session.merge(user)
                        user.is_present = False
                        await session.commit()

                    if len(top_users) == 5:
                        break

                async for user in db.read_bottom_iqs(ctx.guild.id):
                    try:
                        member = await ctx.guild.fetch_member(user.user_id)
                    except:
                        member = None

                    if member:
                        if member.id not in top_users:
                            bottom_users[member.id] = (member.display_name, user.iq)
                        else:
                            break
                    else:
                        await session.merge(user)
                        user.is_present = False
                        await session.commit()

                    if len(bottom_users) == 5:
                        break

                await session.commit()

            if not top_users and not bottom_users:
                await ctx.respond("No qualifying members found.")
                return

            message = "## Top IQs\n"
            for name, iq in top_users.values():
                message += f"- {name}: {iq} IQ\n"

            if bottom_users:
                message += "\n## Bottom IQs\n"
                for name, iq in sorted(bottom_users.values(), key=lambda x: -x[1]):
                    message += f"- {name}: {iq} IQ\n"

            await ctx.respond(message)

        except Exception as e:
            logger.error(f"Error in top command: {e}")
            await ctx.respond("Error retrieving IQ data.")


def setup(bot):
    bot.add_cog(IQ(bot))
