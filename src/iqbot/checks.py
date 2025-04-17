from discord.ext.commands import Context

from senor_bot.config import settings, whitelist


def bot_manager(ctx: Context):
    return (
        ctx.author.id == settings.bot.owner.id
        or ctx.author.guild.permissions.administrator  # type: ignore
        # TODO: add role check
    )
