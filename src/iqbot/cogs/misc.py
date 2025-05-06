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
                "You are given a chronological conversation and a prompt listing specific users. "
                "For each user named in the prompt, write a steelman summary: reconstruct the strongest, most coherent version of their argument in your own phrasing. "
                "Do NOT summarize, quote, or reference any user who is NOT explicitly named in the prompt. "
                "Do NOT narrate what was said—synthesize and refine each named user's reasoning into its best possible form. "
                "Use clear headings for each named user. "
                "Hard constraint: your entire response must be under 2000 characters. "
                "To stay within this limit, prioritize substance, remove repetition, and trim soft qualifiers."
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
