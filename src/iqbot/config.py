import os
from pprint import pprint

from box import Box
from dynaconf import Dynaconf
from icecream import ic

# ic.disable()

config_files = ["settings.toml"]
if os.path.exists(".secrets.toml"):
    config_files.append(".secrets.toml")

settings = Dynaconf(
    envvar_prefix="DYNACONF",
    settings_files=config_files,
    load_dotenv=True,
)

whitelist = {config.guild: config for config in settings.bot.whitelist}

if "tokens" not in settings:
    settings.tokens = Box()

if "BOT_TOKEN" in os.environ:
    settings.tokens.bot = os.environ["BOT_TOKEN"]

if "GPT_TOKEN" in os.environ:
    settings.tokens.gpt = os.environ["GPT_TOKEN"]

if settings.tokens.bot == None or settings.tokens.gpt == None:
    raise Exception(
        "config: BOT_TOKEN and GPT_TOKEN must be specified in .secrets.toml or as environment variables"
    )

if __name__ == "__main__":
    pprint(dict(settings))
