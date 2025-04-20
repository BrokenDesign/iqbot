import datetime
import re
from datetime import datetime, timedelta
from pprint import pformat

import discord
from discord import Member, Message
from discord.ext import commands, tasks
from discord.ext.commands import Bot, Context
from icecream import ic
from loguru import logger
from openai import OpenAI
from sqlalchemy import select

from iqbot import db, gpt
from iqbot.checks import bot_manager
from iqbot.config import settings
from iqbot.db import Bet, User


class Betting(commands.Cog):
    bot: commands.Bot
    muted: bool
    whitelist: dict[int, int]

    def __init__(self, bot: Bot, **kwargs):
        self.client = OpenAI(api_key=settings.tokens.gpt)
        self.bot = bot

    @tasks.loop(minutes=1)
    async def bet_timer(self):
        async with db.get_session() as session:
            open_bets = await session.execute(select(Bet).where(Bet.is_open == True))
            for bet in open_bets.scalars().all():
                if datetime.now() - bet.timestamp > timedelta(minutes=10):
                    bet.is_open = False
            await session.commit()

    async def accept_bet(self, reaction, user, bet):
        try:
            async with db.get_session() as session:
                bet = await session.merge(bet)
                bet.is_open = False
                user1 = await reaction.message.guild.fetch_member(bet.user_id_1)
                user2 = await reaction.message.guild.fetch_member(bet.user_id_2)
                prompt = f"Who won the argument, {user1.display_name} or {user2.display_name}?"
                gpt_response = await gpt.send_prompt(reaction, prompt)
                winner = gpt_response.split()[0]
                if winner == user1.display_name:
                    bet.winner = bet.user_id_1
                elif winner == user2.display_name:
                    bet.winner = bet.user_id_2
                else:
                    logger.error(
                        f"GPT response did not match either user: {gpt_response} not in ({user1.display_name}, {user2.display_name})"
                    )
                    await reaction.message.channel.send(
                        f"**Error: GPT response did not match either user. {reaction.message.jump_url}**"
                    )
                await session.commit()
        except Exception as e:
            logger.error(f"Error in on_reaction_add: {e}")
            await reaction.message.channel.send(
                f"**Error occurred while processing the bet. {reaction.message.jump_url}**"
            )

    async def decline_bet(self, reaction, user, bet):
        try:
            async with db.get_session() as session:
                bet = await session.merge(bet)
                bet.is_open = False
                await session.commit()
                await reaction.message.channel.send(
                    f"**{user.mention} has declined the bet of {bet.bet} IQ against {reaction.message.author.mention}.**"
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

        elif reaction.emoji not in ["✅", "❌"]:
            return

        bet = await db.read_bet(reaction.message.id)
        if bet is None:
            return

        if user.id != bet.user_id_2:
            await reaction.message.remove_reaction(reaction.emoji, user)
            return

        if reaction.emoji == "✅":
            await self.accept_bet(reaction, user, bet)

        elif reaction.emoji == "❌":
            await self.decline_bet(reaction, user, bet)

        else:
            return

    @commands.slash_command(name="bet", description="Initiates a bet between two users")
    async def bet(self, ctx, member: Member, bet_amount: int):
        if ctx.author == member:
            await ctx.respond("You cannot bet against yourself!!")
            return
        if ctx.author == ctx.bot:
            await ctx.respond("You cannot bet against the bot!!")
            return
        if bet_amount <= 0:
            await ctx.respond("Bet amount must be greater than 0")
            return

        response = await ctx.respond(
            f"{member.mention} you have been challenged by {ctx.author.mention} to bet {bet_amount} IQ.\n\n DO YOU ACCEPT? OR ARE YOU A PUSSY??",
        )

        message = await response.original_response()

        await message.add_reaction("✅")
        await message.add_reaction("❌")

        async with db.get_session() as session:
            bet = Bet(
                message_id=message.id,
                timestamp=message.created_at,
                user_id_1=message.author.id,
                user_id_2=member.id,
                bet=bet_amount,
            )
            session.add(bet)
            await session.commit()
            logger.info(f"Bet added to DB: {bet}")


def setup(bot: commands.Bot):
    bot.add_cog(Betting(bot))
