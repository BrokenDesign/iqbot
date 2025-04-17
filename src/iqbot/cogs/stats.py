# type: ignore
import logging
import os
import tempfile
from enum import Enum, auto
from typing import Optional

import polars as pl
from discord import File, Member, User
from discord.ext import commands
from discord.ext.commands import Context
from PIL import Image, ImageDraw, ImageFont
from polars import DataFrame, col

from senor_bot import db


class StatsType(Enum):
    SINGLE = auto()
    MULTIPLE = auto()


class Stats(commands.Cog):
    bot: commands.Bot

    def __init__(self, bot):
        self.bot = bot

    async def __safe_fetch_user(self, ctx: Context, id: int) -> str:
        try:
            if ctx.guild:
                member = await ctx.guild.fetch_member(id)
                if member and member.display_name:
                    return member.display_name

            user = await self.bot.fetch_user(id)
            if user and user.display_name:
                return user.display_name
            else:
                return "unknown"
        except Exception as e:
            logging.error(f"Error in __safe_fetch_user: {e}")
            return "unknown"

    async def process_guild_stats(
        self, ctx: Context, df: DataFrame, user: Optional[User] = None
    ) -> DataFrame:
        try:

            def format_nick(nick: str) -> str:
                if len(nick) > 25:
                    return nick[0:22] + "..."
                else:
                    return nick.ljust(25)

            lookup = {
                value: await self.__safe_fetch_user(ctx, value)
                for value in df["mentions_id"].unique()
            }
            result = (
                df.groupby(col(["mentions_id"]))
                .agg(
                    pl.count().alias("num_questions"),
                    (col("num_replies").sum() / pl.count()).alias("avg_replies"),
                    (col("has_answer").sum() / pl.count()).alias("answer_rate"),
                )
                .sort([col("avg_replies"), -col("answer_rate"), -col("num_questions")])
                .with_columns(col("mentions_id").map_dict(lookup).alias("member"))
                .with_row_count(offset=1)
                .select(
                    col("mentions_id"),
                    col("row_nr").alias("rank"),
                    col("member").apply(format_nick).alias("member"),
                    col("num_questions").alias("num_questions"),
                    col("avg_replies").round(0).cast(pl.Int64).alias("avg_replies"),
                    col("answer_rate")
                    .apply(lambda x: f"{x:.1%}")
                    .alias("pct_answered"),
                )
            )
            if user is not None:
                result = result.filter(col("mentions_id") == user.id)

            result = result.drop("mentions_id")

            return result
        except Exception as e:
            logging.error(f"Error in process_guild_stats: {e}")
            return None

    async def data_to_text(self, df: DataFrame) -> str:
        try:
            return "\n".join(str(df).split("\n")[1::])
        except Exception as e:
            logging.error(f"Error in data_to_text: {e}")
            return ""

    async def text_to_image(self, text, image_size=(580, 240)) -> Image:
        try:
            font_size = 12
            font_path = "CascadiaMono.ttf"
            background_color = "#2a2e36"
            text_color = "white"

            image = Image.new("RGB", image_size, background_color)
            draw = ImageDraw.Draw(image)
            font = ImageFont.truetype(font_path, font_size)
            draw.text((5, 0), text, font=font, fill=text_color)

            return image
        except Exception as e:
            logging.error(f"Error in text_to_image: {e}")
            return None

    async def get_stats_image(self, df: DataFrame, type: StatsType) -> Image:
        try:
            if type == StatsType.MULTIPLE:
                size = (580, 240)
            elif type == StatsType.SINGLE:
                size = (580, 112)
            else:
                raise ValueError("Unhandled value of StatsType")

            text = await self.data_to_text(df)
            image = await self.text_to_image(text, size)

            return image
        except Exception as e:
            logging.error(f"Error in get_stats_image: {e}")
            return None

    async def respond_with_image(self, ctx: Context, image: Image) -> None:
        out = tempfile.NamedTemporaryFile(
            dir=os.environ["BOT_TEMP_DIR"], prefix="stats.", suffix=".png", delete=False
        )
        out.flush()
        try:
            image.save(out.name, format="PNG")
            file = File(out.name, filename="stats.png")
            await ctx.respond(file=file)
        except Exception as err:
            print(err)
        finally:
            out.close()

    @commands.slash_command(name="top", description="output the top/bottom users")
    async def get_guild_stats(self, ctx: Context):
        if ctx.guild is None:
            return await ctx.respond("Command only available in server")
        else:
            df = await db.read_guild(ctx)
            df = await self.process_guild_stats(ctx, df)
            image = await self.get_stats_image(df, StatsType.MULTIPLE)
            await self.respond_with_image(ctx, image)

    @commands.slash_command(name="user", description="get user stats")
    async def get_user_stats(self, ctx: Context, user: Member):
        if ctx.guild is None:
            await ctx.respond("error: command only available in server")
            return
        elif user is None:
            await ctx.respond("error: must specify user")
            return

        df = await db.read_guild(ctx)
        df = await self.process_guild_stats(ctx, df, user)

        if df.shape[0] == 0:
            await ctx.respond(f"No entry for {user.nick}")
            return

        image = await self.get_stats_image(df, StatsType.SINGLE)
        await self.respond_with_image(ctx, image)


def setup(bot: commands.Bot):
    bot.add_cog(Stats(bot))
