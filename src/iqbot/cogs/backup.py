import asyncio
import gzip
import os
import re
import shutil
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import discord
from discord.commands import Option, SlashCommandGroup
from discord.ext import commands, tasks
from loguru import logger

from iqbot.checks import bot_owner
from iqbot.config import settings


def create_backup() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{timestamp}.sqlite3.gz"
    path = os.path.join(settings.database.backup_dir, filename)

    with (
        open(urlparse(settings.database.url).path.lstrip("/"), "rb") as f_in,
        gzip.open(path, "wb") as f_out,
    ):
        shutil.copyfileobj(f_in, f_out)

    logger.info(f"Created backup: {filename}")
    remove_old_backups()
    return filename


def remove_old_backups():
    now = datetime.now()
    for backup in os.listdir(settings.database.backup_dir):
        try:
            match = re.search(r"^backup_(\d+_\d+)\.sqlite3\.gz$", backup)
            if not match:
                logger.warning(f"Failed to match timestamp in filename: {backup}")
                continue
            dt = datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")
            if (now - dt) > timedelta(days=settings.database.retention):
                os.remove(os.path.join(settings.database.backup_dir, backup))
                logger.info(f"Deleted old backup: {backup}")
        except Exception as e:
            logger.warning(f"Failed to parse or delete backup `{backup}`: {e}")


async def get_backup_choices(
    ctx: discord.AutocompleteContext,
) -> list[discord.OptionChoice]:
    try:
        query = ctx.value
        files = sorted(
            f
            for f in os.listdir(settings.database.backup_dir)
            if f.endswith(".gz") and query.lower() in f.lower()
        )
        return [discord.OptionChoice(name=f, value=f) for f in files[:25]]
    except Exception as e:
        logger.error(f"Autocomplete failed: {e}")
        return []


class Backup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        os.makedirs(settings.database.backup_dir, exist_ok=True)
        self.backup_task.start()

    def cog_unload(self):
        self.backup_task.cancel()
        logger.info("Backup cog unloaded and task cancelled.")

    backup = SlashCommandGroup("backup", "Backup management commands")

    @backup.command(name="save", description="Create a backup now")
    @commands.check(bot_owner)
    async def backup_save(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        try:
            name = create_backup()
            await ctx.respond(f"Backup created: `{name}`", ephemeral=True)
        except Exception as e:
            logger.error(f"Manual backup failed: {e}")
            await ctx.respond(f"Failed to create backup: {e}", ephemeral=True)

    @backup.command(name="list", description="List all available backups")
    @commands.check(bot_owner)
    async def backup_list(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        try:
            files = sorted(
                f for f in os.listdir(settings.database.backup_dir) if f.endswith(".gz")
            )
            if not files:
                await ctx.respond("No backups found.", ephemeral=True)
                return
            msg = "\n".join(f"- {f}" for f in files)
            await ctx.respond(msg, ephemeral=True)
            logger.info(f"Listed {len(files)} backups.")
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            await ctx.respond(f"Error listing backups: {e}", ephemeral=True)

    @backup.command(name="restore", description="Restore a backup by name")
    @commands.check(bot_owner)
    async def backup_restore(
        self,
        ctx: discord.ApplicationContext,
        filename: Any = Option(
            str, "Backup file to restore", autocomplete=get_backup_choices
        ),
    ):
        await ctx.defer(ephemeral=True)
        path = os.path.join(settings.database.backup_dir, filename)
        if not os.path.isfile(path):
            await ctx.respond(f"Backup `{filename}` not found.", ephemeral=True)
            logger.warning(f"Attempted to restore missing backup: {filename}")
            return
        try:
            with (
                gzip.open(path, "rb") as f_in,
                open(urlparse(settings.database.url).path.lstrip("/"), "wb") as f_out,
            ):
                shutil.copyfileobj(f_in, f_out)
            await ctx.respond(
                f"Backup `{filename}` restored successfully.", ephemeral=True
            )
            logger.info(f"Restored backup: {filename}")
        except Exception as e:
            logger.error(f"Restore failed for `{filename}`: {e}")
            await ctx.respond(f"Failed to restore backup: {e}", ephemeral=True)

    @backup.command(name="remove", description="Delete a backup by name")
    @commands.check(bot_owner)
    async def backup_remove(
        self,
        ctx: discord.ApplicationContext,
        filename: Any = Option(
            str, "Backup file to delete", autocomplete=get_backup_choices
        ),
    ):
        await ctx.defer(ephemeral=True)
        path = os.path.join(settings.database.backup_dir, filename)

        if not os.path.isfile(path):
            await ctx.respond(f"Backup `{filename}` not found.", ephemeral=True)
            logger.warning(f"Tried to remove non-existent backup: {filename}")
            return

        try:
            os.remove(path)
            await ctx.respond(f"Backup `{filename}` has been removed.", ephemeral=True)
            logger.info(f"Deleted backup: {filename}")
        except Exception as e:
            logger.error(f"Failed to delete backup `{filename}`: {e}")
            await ctx.respond(f"Failed to delete backup: {e}", ephemeral=True)

    @tasks.loop(hours=24)
    async def backup_task(self):
        try:
            name = create_backup()
            logger.info(f"Daily backup created: {name}")
        except Exception as e:
            logger.error(f"Scheduled backup failed: {e}")

    @backup_task.before_loop
    async def before_backup_task(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(24 * 60 * 60)


def setup(bot):
    bot.add_cog(Backup(bot))
