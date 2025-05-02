import tempfile
from typing import Optional

from discord import File
from discord.commands import SlashCommandGroup
from discord.ext import commands
from discord.ext.commands import Context
from loguru import logger

from iqbot import db, gpt
from iqbot.checks import bot_owner
from iqbot.config import settings


class Owner(commands.Cog):
    bot: commands.Bot

    def __init__(self, bot):
        self.bot = bot

    owner = SlashCommandGroup("owner", "Owner only commands")

    def parse_message_link(self, message_link: str):
        try:
            parts = message_link.split("/")
            channel_id = int(parts[-2])
            message_id = int(parts[-1])
            return channel_id, message_id
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing message link: {e}")
            return None, None

    async def respond_with_file(self, ctx: Context, content: str) -> None:
        out = tempfile.NamedTemporaryFile(
            dir=".", prefix="conversation.", suffix=".txt", delete=False
        )
        out.write(content.encode("utf-8"))
        out.flush()
        try:
            file = File(out.name, filename="conversation.txt")
            await ctx.respond(file=file)  # type: ignore
        except Exception as err:
            print(err)
        finally:
            out.close()

    @commands.slash_command(
        name="sync", description="Sync slash commands to whitelisted guilds"
    )
    @commands.check(bot_owner)
    async def sync(self, ctx):
        try:
            await ctx.defer(ephemeral=True)
            authorized_guilds = {entry.guild for entry in settings.bot.whitelist}
            present_guilds = [
                guild.id for guild in self.bot.guilds if guild.id in authorized_guilds
            ]
            await self.bot.sync_commands(guild_ids=present_guilds)
            await ctx.respond(
                f"Synced commands to {len(present_guilds)} authorized guild(s)."
            )
        except Exception as e:
            logger.error(f"Error syncing commands: {e}")
            await ctx.respond("Failed to sync commands.")

    @owner.command(name="dump", description="Outputs the last N messages")
    @commands.check(bot_owner)
    async def dump(self, ctx, num_messages: int, message_link: Optional[str]):
        message = None

        if message_link is not None:
            try:
                channel_id, message_id = self.parse_message_link(message_link)
                if channel_id is None or message_id is None:
                    await ctx.respond("Invalid message link format")
                    return

                message = await ctx.guild.get_channel(channel_id).fetch_message(
                    message_id
                )
                if message is None:
                    await ctx.respond("Message not found")
                    return

                conversation = await gpt.read_message_context(message)
                if num_messages < conversation.count("\n"):
                    conversation = "\n".join(conversation.split("\n")[-num_messages:])
                if len(conversation) >= 2000:
                    await self.respond_with_file(ctx, conversation)
                else:
                    await ctx.respond(conversation)
            except Exception as e:
                logger.error(f"Error in dump command: {e}")
                await ctx.respond("Failed to get the conversation history")
            return

        else:
            try:
                conversation = await gpt.read_current_context(ctx)
                if num_messages < conversation.count("\n"):
                    conversation = "\n".join(conversation.split("\n")[-num_messages:])
                    if len(conversation) >= 2000:
                        await self.respond_with_file(ctx, conversation)
                    else:
                        await ctx.respond(conversation)
            except Exception as e:
                logger.error(f"Error in dump command: {e}")
                await ctx.respond("Failed to get the conversation history")

    @owner.command(name="reset", description="full reset of the database")
    @commands.check(bot_owner)
    async def reset(self, ctx, confirmation: str):
        if confirmation != "CONFIRM":
            await ctx.respond(
                "Please confirm the reset by typing 'CONFIRM' as the argument.",
                ephemeral=True,
            )
            return
        try:
            await ctx.defer(ephemeral=True)
            await db.async_main()
            await ctx.respond("Database reset complete")
        except Exception as e:
            logger.error(f"Error in question command: {e}")
            await ctx.respond("Failed to get a response from GPT")


def setup(bot):
    bot.add_cog(Owner(bot))
