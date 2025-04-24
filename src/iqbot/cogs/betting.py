import datetime
import re
from datetime import datetime, timedelta
from pprint import pformat

from discord import Member
from discord.ext import commands, tasks
from discord.ext.commands import Bot
from loguru import logger
from openai import OpenAI
from sqlalchemy import select

from iqbot import db, gpt
from iqbot.db import Bet


class Betting(commands.Cog):
    bot: commands.Bot
    muted: bool
    whitelist: dict[int, int]

    def __init__(self, bot: Bot, **kwargs):
        self.bot = bot

    @tasks.loop(minutes=1)
    async def bet_timer(self):
        async with db.get_session() as session:
            open_bets = await session.execute(select(Bet).where(Bet.is_open == True))
            for bet in open_bets.scalars().all():
                if datetime.now() - bet.timestamp > timedelta(minutes=1):
                    logger.info(f"Deleting bet {bet.message_id} after 10 minutes")
                    await session.delete(bet)
            await session.commit()

    async def accept_bet(self, reaction, user, bet):
        try:
            async with db.get_session() as session:
                has_winner = False
                bet = await session.merge(bet)
                bet.is_open = False

                member1 = await reaction.message.guild.fetch_member(bet.user_id_1)
                member2 = await reaction.message.guild.fetch_member(bet.user_id_2)

                user1 = await session.merge(
                    await db.read_or_add_user(bet.guild_id, bet.user_id_1)
                )
                user2 = await session.merge(
                    await db.read_or_add_user(bet.guild_id, bet.user_id_2)
                )

                prompt = f"Who won the argument, {member1.name} or {member2.name}?"
                gpt_response = await gpt.send_prompt(reaction, prompt)
                match = re.search(r"(?<=winner:\s).+(?=\*\*)", gpt_response.lower())

                logger.info("GPT response: " + gpt_response)
                logger.info("Match: " + str(match))

                gpt_response = gpt_response.replace(member1.name, member1.display_name)
                gpt_response = gpt_response.replace(member2.name, member2.display_name)

                if match is not None:
                    winner = match.group(0).strip()
                else:
                    winner = "error"

                if winner == member1.name:
                    has_winner = True
                    bet.winner = bet.user_id_1
                    user1.iq += bet.bet
                    user2.iq -= bet.bet
                    await session.commit()
                elif winner == member2.name:
                    has_winner = True
                    bet.winner = bet.user_id_2
                    user1.iq -= bet.bet
                    user2.iq += bet.bet
                    await session.commit()
                elif winner.lower() == "draw":
                    await session.delete(bet)
                    await session.commit()
                else:
                    await session.delete(bet)
                    await session.commit()
                    logger.error(
                        f"GPT response did not match either user: {winner} not in ({member1.display_name}, {member2.display_name}, draw)"
                    )
                    await reaction.message.channel.send(
                        f"**Error: GPT response did not match either user. {reaction.message.jump_url}**"
                    )
                    return
                await reaction.message.channel.send(gpt_response[0:1999])
                if has_winner:
                    await reaction.message.channel.send(
                        f"{member1.mention} **IQ -> {user1.iq}**\n{member2.mention} **IQ -> {user2.iq}**"
                    )

        except Exception as e:
            await session.delete(bet)
            await session.commit()
            logger.error(f"Error in on_reaction_add: {e}")
            await reaction.message.channel.send(
                f"**Error occurred while processing the bet. {reaction.message.jump_url}**"
            )

    async def decline_bet(self, reaction, user, bet):
        try:
            async with db.get_session() as session:
                bet = await session.merge(bet)
                await session.delete(bet)
                await session.commit()
                await reaction.message.channel.send(
                    f"**{user.mention} has declined the bet of {bet.bet} IQ against {reaction.message.mentions[1].mention}.**"
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
                guild_id=ctx.guild.id,
                message_id=message.id,
                timestamp=message.created_at,
                user_id_1=ctx.author.id,
                user_id_2=member.id,
                bet=bet_amount,
            )
            session.add(bet)
            await session.commit()
            logger.info(f"Bet added to DB: {bet}")


def setup(bot: commands.Bot):
    bot.add_cog(Betting(bot))
