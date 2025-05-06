import datetime
import re
from datetime import datetime, timedelta
from enum import Enum
from math import sqrt
from typing import Any

from discord import ApplicationContext, Member
from discord.commands import Option
from discord.ext import commands, tasks
from discord.ext.commands import Bot
from loguru import logger
from sqlalchemy import select

from iqbot import db, gpt
from iqbot.checks import bot_manager, bot_owner
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
        self.bet_timer.start()

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

    def calculate_k(self, user: User) -> float:
        assert user.iq is not None
        deviation = abs(user.iq - 100)
        base_k = max(6, 16 - (deviation / 10))
        return max(base_k / sqrt(max(user.num_bets, 1)), 1)

    async def update_elo(
        self, user1: User, user2: User, result: BetResult
    ) -> tuple[User, User]:
        if result in (BetResult.NONE, BetResult.ERROR):
            raise ValueError("Invalid result value")

        assert user1.iq is not None
        assert user2.iq is not None

        expected1 = 1 / (1 + 10 ** ((user2.iq - user1.iq) / settings.elo.scale))
        expected2 = 1 - expected1

        delta1 = self.calculate_k(user1) * (result.value - expected1)
        delta2 = self.calculate_k(user2) * ((1 - result.value) - expected2)

        delta1 = max(min(delta1, settings.elo.max_delta), -settings.elo.max_delta)
        delta2 = max(min(delta2, settings.elo.max_delta), -settings.elo.max_delta)

        user1.iq = round(user1.iq + delta1)
        user2.iq = round(user2.iq + delta2)

        user1.num_bets += 1
        user2.num_bets += 1

        return user1, user2

    @tasks.loop(minutes=30)
    async def bet_timer(self) -> None:
        async with db.get_session() as session:
            result = await session.execute(select(Bet))
            bets = result.scalars()
            for bet in bets:
                if datetime.now() - bet.timestamp > timedelta(minutes=10):
                    logger.info(f"Deleting bet {bet.message_id} after 10 minutes")
                    await session.delete(bet)
            await session.commit()

    @bet_timer.before_loop
    async def before_backup_task(self):
        await self.bot.wait_until_ready()

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
                gpt_response = await gpt.send_prompt(
                    reaction, settings.gpt.system_prompt, prompt
                )
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
                    f"{member1.display_name}\n{member1.mention} **IQ {start_iq1} -> {user1.iq}**\n{member2.mention} **IQ {start_iq2} -> {user2.iq}**"
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
        if user.bot:
            return

        if reaction.message.author != self.bot.user:
            return

        if reaction.emoji not in ["✅", "❌"]:
            logger.info(f"Reaction added: {reaction.emoji} by {user.name}")
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
    async def bet(self, ctx: ApplicationContext, member: Member):
        if ctx.author == member:
            await ctx.respond("You cannot bet against yourself!!")
            return
        if ctx.author == ctx.bot:
            await ctx.respond("You cannot bet against the bot!!")
            return

        await ctx.respond(
            f"{member.mention} you have been challenged by {ctx.author.mention} to bet IQ.\n\n DO YOU ACCEPT? OR ARE YOU A PUSSY??",
        )

        message = await ctx.interaction.original_response()

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

    @commands.command(
        name="evaluate",
        description="Evaluates a debate against a given debate topic (admin only)",
    )
    @commands.check(bot_manager)
    async def evaluate(
        self, ctx: ApplicationContext, member1: Member, member2: Member, *, topic: str
    ):
        if member1 == member2:
            await ctx.channel.send("You cannot evaluate a bet between the same user!")
            return

        try:
            prompt = f"Evaluate the debate between {member1.name} and {member2.name} on the topic: {topic}. Include the topic in the response."
            gpt_response = await gpt.send_prompt(
                ctx, settings.gpt.system_prompt, prompt
            )
            match = re.search(r"(?<=winner:\s).+(?=\*\*)", gpt_response.lower())

            winner = match.group(0).strip() if match is not None else "error"
            result = self.resolve_winner(member1, member2, winner)

            if result in (BetResult.USER1, BetResult.USER2, BetResult.DRAW):
                async with db.get_session() as session:
                    user1 = await db.read_or_add_user(ctx.guild.id, member1.id)
                    user2 = await db.read_or_add_user(ctx.guild.id, member2.id)
                    user1, user2 = await self.update_elo(user1, user2, result)
                    user1 = await session.merge(user1)
                    user2 = await session.merge(user2)
                    await session.commit()

            await ctx.channel.send(gpt_response[0:1999])

        except Exception as e:
            logger.error(f"Error in evaluate command: {e}")
            await ctx.channel.send(f"**Error occurred while evaluating debate.**")


def setup(bot: commands.Bot):
    bot.add_cog(Betting(bot))
