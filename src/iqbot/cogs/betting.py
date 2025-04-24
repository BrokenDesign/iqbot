import datetime
import re
from datetime import datetime, timedelta
from enum import Enum

from discord import Member
from discord.ext import commands, tasks
from discord.ext.commands import Bot
from loguru import logger
from sqlalchemy import select

from iqbot import db, gpt
from iqbot.config import settings
from iqbot.db import Bet, User


class BetResult(Enum):
    USER1 = 1
    USER2 = 0
    DRAW = 0.5
    NONE = None
    ERROR = None


class Betting(commands.Cog):
    bot: commands.Bot
    muted: bool
    whitelist: dict[int, int]

    def __init__(self, bot: Bot, **kwargs):
        self.bot = bot

    def resolve_winner(
        self, member1: Member, member2: Member, winner: str
    ) -> BetResult:
        winner_map = {
            member1.name.lower(): BetResult.USER1,
            member2.name.lower(): BetResult.USER2,
            "draw": BetResult.DRAW,
            "none": BetResult.NONE,
        }
        return winner_map.get(winner.lower(), BetResult.ERROR)

    async def update_elo(
        self, user1: User, user2: User, result: BetResult
    ) -> tuple[User, User]:
        if result in (BetResult.NONE, BetResult.ERROR):
            raise ValueError("Invalid result value")

        assert user1.iq is not None
        assert user2.iq is not None

        expected1 = 1 / (1 + 10 ** ((user2.iq - user1.iq) / settings.elo.scale))
        expected2 = 1 - expected1

        delta1 = settings.elo.k * (result.value - expected1)
        delta2 = settings.elo.k * ((1 - result.value) - expected2)

        delta1 = max(min(delta1, settings.elo.max_delta), -settings.elo.max_delta)
        delta2 = max(min(delta2, settings.elo.max_delta), -settings.elo.max_delta)

        user1.iq = round(user1.iq + delta1)
        user2.iq = round(user2.iq + delta2)

        return user1, user2

    @tasks.loop(minutes=1)
    async def bet_timer(self) -> None:
        async with db.get_session() as session:
            open_bets = await session.execute(select(Bet).where(Bet.is_open == True))
            for bet in open_bets.scalars().all():
                if datetime.now() - bet.timestamp > timedelta(minutes=1):
                    logger.info(f"Deleting bet {bet.message_id} after 10 minutes")
                    await session.delete(bet)
            await session.commit()

    async def accept_bet(self, reaction, bet) -> None:
        try:
            async with db.get_session() as session:
                bet = await session.merge(bet)

                member1 = await reaction.message.guild.fetch_member(bet.user_id_1)
                member2 = await reaction.message.guild.fetch_member(bet.user_id_2)

                user1 = await db.read_or_add_user(bet.guild_id, bet.user_id_1)
                user2 = await db.read_or_add_user(bet.guild_id, bet.user_id_2)

                start_iq1 = user1.iq
                start_iq2 = user2.iq

                prompt = f"Who won the argument, {member1.name} or {member2.name}?"
                gpt_response = await gpt.send_prompt(reaction, prompt)
                match = re.search(r"(?<=winner:\s).+(?=\*\*)", gpt_response.lower())

                gpt_response = gpt_response.replace(member1.name, member1.display_name)
                gpt_response = gpt_response.replace(member2.name, member2.display_name)

                winner = match.group(0).strip() if match is not None else "error"
                result = self.resolve_winner(member1, member2, winner)

                if result in (BetResult.USER1, BetResult.USER2, BetResult.DRAW):
                    user1, user2 = await self.update_elo(user1, user2, result)
                    user1 = await session.merge(user1)
                    user2 = await session.merge(user2)
                    await session.commit()

                await reaction.message.channel.send(gpt_response[0:1999])
                await reaction.message.channel.send(
                    f"{member1.mention} **IQ {start_iq1} -> {user1.iq}**\n{member2.mention} **IQ {start_iq2} -> {user2.iq}**"
                )

        except Exception as e:
            await session.delete(bet)
            await session.commit()
            logger.error(f"Error in on_reaction_add: {e}")
            await reaction.message.channel.send(
                f"**Error occurred while processing the bet. {reaction.message.jump_url}**"
            )

    async def decline_bet(self, reaction, user, bet) -> None:
        try:
            async with db.get_session() as session:
                bet = await session.merge(bet)
                await session.delete(bet)
                await session.commit()
                await reaction.message.channel.send(
                    f"**{user.mention} has declined the bet against {reaction.message.mentions[1].mention}.**"
                )
        except Exception as e:
            logger.error(f"Error in on_reaction_add: {e}")
            await reaction.message.channel.send(
                f"**Error occurred while processing the bet. {reaction.message.jump_url}**"
            )

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        logger.info(f"Reaction added: {reaction.emoji} by {user.name}")
        if user.bot:
            return

        if reaction.message.author != self.bot.user:
            return

        elif reaction.emoji not in ["✅", "❌"]:
            await reaction.message.remove_reaction(reaction.emoji, user)
            return

        bet = await db.read_bet(reaction.message.id)
        if bet is None:
            return

        if user.id != bet.user_id_2:
            await reaction.message.remove_reaction(reaction.emoji, user)
            return

        if reaction.emoji == "✅":
            await self.accept_bet(reaction, bet)

        elif reaction.emoji == "❌":
            await self.decline_bet(reaction, user, bet)

        else:
            return

    @commands.slash_command(name="bet", description="Initiates a bet between two users")
    async def bet(self, ctx, member: Member):
        if ctx.author == member:
            await ctx.respond("You cannot bet against yourself!!")
            return
        if ctx.author == ctx.bot:
            await ctx.respond("You cannot bet against the bot!!")
            return

        response = await ctx.respond(
            f"{member.mention} you have been challenged by {ctx.author.mention} to bet IQ.\n\n DO YOU ACCEPT? OR ARE YOU A PUSSY??",
        )

        message = await response.original_response()

        await message.add_reaction("✅")
        await message.add_reaction("❌")

        async with db.get_session() as session:
            bet = Bet(
                guild_id=ctx.guild.id,
                message_id=message.id,
                timestamp=message.created_at,
                user_id_1=ctx.author.id,
                user_id_2=member.id,
            )
            session.add(bet)
            await session.commit()
            logger.info(f"Bet added to DB: {bet}")


def setup(bot: commands.Bot):
    bot.add_cog(Betting(bot))
