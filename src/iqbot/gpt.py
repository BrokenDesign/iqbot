from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from discord import Message, Reaction
from discord.ext.commands import Context
from loguru import logger
from openai import OpenAI

from iqbot.config import settings

client = OpenAI(api_key=settings.tokens.gpt)


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage:
    role: Role
    content: str

    def __init__(self, role: Role, content: str) -> None:
        self.role = role
        self.content = content

    def to_dict(self) -> dict:
        return self.__dict__


async def read_current_context(ctx: Context) -> str:
    messages = []
    async for message in ctx.channel.history(
        before=datetime.now(),
        after=datetime.now() - timedelta(minutes=settings.gpt.history.minutes),
        limit=settings.gpt.history.messages,
        oldest_first=False,
    ):
        if message.author.bot:
            continue
        messages.append(f"{message.author.display_name}: {message.content}")

    return "\n".join(messages[::-1])


async def read_reaction_context(reaction: Reaction) -> str:
    messages = []
    async for message in reaction.message.channel.history(
        before=reaction.message.created_at,
        after=reaction.message.created_at
        - timedelta(minutes=settings.gpt.history.minutes),
        limit=settings.gpt.history.messages,
        oldest_first=False,
    ):
        if message.author.bot:
            continue
        messages.append(f"{message.author.display_name}: {message.content}")

    return "\n".join(messages[::-1])


async def build_prompt(conversation: str, command_prompt: str) -> list[ChatMessage]:
    messages = [
        ChatMessage(
            role=Role.SYSTEM,
            content="Play the role of a fair judge and evaluate the arguments made by two sides, avoid fence sitting and placating, "
            "do not take statements to be inherently true and evaluate their validity yourself, give a verdict on which side is more correct in relation to the topic, "
            "also evaluate the effectiveness of their argument"
            "You should refer to users with the exact unicode characters provided in the conversation. "
            "When asked for a winner you should respond with the name of the winner as the first word of your response. "
            "You should only pick a winner if asked for one."
            f"Please limit your responses to {settings.gpt.max_tokens} tokens.",
        ),
        ChatMessage(
            role=Role.USER,
            content=f"Based on the following conversation: \n\n{conversation}\n\n please answer: {command_prompt}.",
        ),
    ]
    return messages


async def send_prompt(ctx: Context | Reaction, command_prompt: str) -> str:
    if isinstance(ctx, Reaction):
        conversation = await read_reaction_context(ctx)
    else:
        conversation = await read_current_context(ctx)

    if not conversation:
        logger.warning("No conversation history found.")
        return "No conversation history available to generate a response."

    messages = await build_prompt(conversation, command_prompt)
    try:
        response = client.chat.completions.create(
            model=settings.gpt.model,
            messages=[message.to_dict() for message in messages],  # type: ignore
            max_tokens=settings.gpt.max_tokens,
        )
        logger.info(f"GPT response: {response.choices[0].message.content}")
        return (
            response.choices[0].message.content
            if response.choices[0].message.content
            else "No response from GPT"
        )
    except Exception as e:
        logger.error(f"Error occurred in send_prompt: {e}")
        return (
            "An error occurred while processing your request. Please try again later."
        )
