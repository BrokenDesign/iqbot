from pathlib import Path
from typing import Any

import tomli
from pydantic import BaseModel
from pydantic_settings import BaseSettings


class Tokens(BaseModel):
    bot: str
    gpt: str


class DatabaseSettings(BaseModel):
    url: str
    echo: bool
    pool_size: int
    max_overflow: int
    pool_recycle: int
    pool_timeout: int


class OwnerSettings(BaseModel):
    id: int


class IntentsSettings(BaseModel):
    guilds: bool
    messages: bool
    message_content: bool
    reactions: bool


class WhitelistEntry(BaseModel):
    guild: int
    channel: int
    roles: list[int]


class BotSettings(BaseModel):
    prefix: str
    temp_dir: str
    cogs: list[str]
    owner: OwnerSettings
    intents: IntentsSettings
    whitelist: list[WhitelistEntry]


class GptHistorySettings(BaseModel):
    minutes: int
    messages: int


class GptTokenSettings(BaseModel):
    limit: int
    overhead_max: int
    output_max: int
    prompt_max: int


class GptSettings(BaseModel):
    model: str
    system_prompt: str
    tokens: GptTokenSettings
    history: GptHistorySettings


class EloSettings(BaseModel):
    k: int
    scale: int
    max_delta: int


class Settings(BaseSettings):
    database: DatabaseSettings
    bot: BotSettings
    gpt: GptSettings
    elo: EloSettings
    tokens: Tokens


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as f:
        return tomli.load(f)


def deep_merge(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            base[key] = deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_settings() -> Settings:
    base_config = load_toml(Path("settings.toml"))
    if Path(".secrets.toml").exists():
        secrets_config = load_toml(Path(".secrets.toml"))
        merged = deep_merge(base_config, secrets_config)
    else:
        merged = base_config
    return Settings(**merged)


settings = load_settings()


if __name__ == "__main__":
    print(settings.model_dump_json(indent=2))
