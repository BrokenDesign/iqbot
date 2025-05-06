import random

from discord import ApplicationContext, Member
from discord.ext import commands
from loguru import logger

from iqbot import gpt


class Misc(commands.Cog):
    bot: commands.Bot

    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="ping", description="checks bot latency")
    async def ping(self, ctx: ApplicationContext):
        try:
            await ctx.respond(f"Pong! ```latency = {round(self.bot.latency, 1)}ms```")
        except Exception as e:
            logger.error(f"Error in ping command: {e}")

    @commands.slash_command(name="topic", description="sends a debate topic")
    async def topic(self, ctx: ApplicationContext):
        with open("resources/debate_topics.txt", "r") as f:
            topics = f.readlines()
            await ctx.respond(random.choice(topics).strip())

    @commands.slash_command(
        name="steelman", description="Gets conversation summary from GPT"
    )
    async def steelman(
        self, ctx: ApplicationContext, member1: Member, member2: Member
    ) -> None:
        await ctx.defer()
        try:
            system_prompt = (
                "You are given a conversation in chronological order. "
                "You will be provided with a prompt naming specific users. "
                "Provide a steelman summary for each of the users mentioned in the prompt and only those users. "
                "You should include headings for each user followed by the steelman of their argument. "
                "Hard constraint: Your entire response must not exceed 2000 characters. "
                "If necessary, prioritize substance, cut repetition, and trim soft qualifiers to stay within this limit."
            )
            prompt = f"Please summarize the conversation between {member1.name} and {member2.name}. \n\n"
            gpt_response = await gpt.send_prompt(ctx, system_prompt, prompt)
            gpt_response = gpt_response.replace(member1.name, member1.display_name)
            gpt_response = gpt_response.replace(member2.name, member2.display_name)
            await ctx.respond(gpt_response[0:1999])

        except Exception as e:
            logger.error(f"Error in on_reaction_add: {e}")
            await ctx.respond("An error occurred while processing your request.")


def setup(bot):
    bot.add_cog(Misc(bot))
