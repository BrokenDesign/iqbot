# type: ignore

import datetime
import re
from datetime import datetime, timedelta
from pprint import pformat

import discord
import openai
from discord import Member, Message
from discord.ext import commands, tasks
from discord.ext.commands import Bot, Context
from icecream import ic
from loguru import logger
from iqbot.checks import bot_manager
from iqbot.config import settings, whitelist
from iqbot.db import Question, write_question


class IQ(commands.Cog):
    bot: commands.Bot
    muted: bool
    whitelist: dict[int, int]

    def __init__(self, bot: Bot, **kwargs):
        openai.api_key = settings.tokens.gpt
        self.bot = bot

    async def read_messages(
        self, ctx: Context, time: timedelta = timedelta(minutes=30), max_messages: int = 100, users: list[Member]
    ) -> list[Message]:
        messages = []
        n_message = 0
        async for message in ctx.channel.history(after=datetime.now() - time):
            if message.author in users and not message.content.startswith(
                settings.bot.prefix
            ):
                messages.append(message)
                n_message += 1
            if n_message >= max_messages:
                break
        return messages


    async def send_prompt(self, ctx: Context, messages: list[Message]) -> str:
        prompt = "Based on the following conversation please answer with only their name which person gave the most correct and logically valid argument.\n\n"
        prompt += "\n".join(
            f"{message.author.name}: {message.content}" for message in messages
        )
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o",
                max_tokens=1,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = response.choices[0].message.content.strip()
            logger.info(f"GPT response: {answer}")
            return answer
        except Exception as e:
            logger.error(f"Error occurred in send_prompt: {e}")
            raise e
        
    @commands.slash_command(name="join", description="Addss a user to the IQ system")
    async def join(self, ctx: Context, user: Member = None):
        if user is None:
            user = ctx.author
        async with async_session() as session:
            iq = await session.execute(
                select(User).where(User.guild_id == ctx.guild.id, User.user_id == user.id)
            )
            iq = iq.scalar_one_or_none()
        if iq is None:
            user_iq = User(ctx)
            async with async_session() as session:
                async with session.begin():
                    session.add(user_iq)
                    await session.commit()
            await ctx.respond(f"User {user.name} has been added to the IQ system")
        else:
            await ctx.respond(f"User {user.name} is already in the IQ system")


    @commands.slash_command(name="iq", description="Returns a users IQ")
    async def iq(self, ctx: Context, user: Member = None):
        if user is None:
            user = ctx.author
        async with async_session() as session:
            iq = await session.execute(
                select(User).where(User.guild_id == ctx.guild.id, User.user_id == user.id)
            )
            iq = iq.scalar_one_or_none()
        if iq is None:
            await ctx.respond(f"User {user.name} has no IQ set")
        else:
            await ctx.respond(f"User {user.name} has {iq.iq} IQ")

    @commands.check(bot_manager)
    @commands.slash_command(
        name="set", description="Sets a users IQ to a specific value"
    )
    async def set_iq(self, ctx: Context, user: Member, iq: int):
        if ctx.author.id != settings.bot.owner.id:
            await ctx.respond("Insufficient permission: Owner required")
        else:
            user_iq = User(ctx, iq)
            async with async_session() as session:
                async with session.begin():
                    session.add(user_iq)
                    await session.commit()
            await ctx.respond(f"User {user.name} has been set to {iq} IQ")


    #TODO: Allow setting of time limit and max_messages either here or through settings commands.
    @commands.check(bot_manager)
    @commands.slash_command(
        name="bet", description="Initiates a bet between two users"
    )
    async def bet(self, ctx: Context, user1: Member, bet1: int, user2: Member, bet2: int):
        if ctx.author.id != settings.bot.owner.id:
            await ctx.respond("Insufficient permission: Owner required")




def setup(bot: commands.Bot):
    bot.add_cog(Questions(bot))
