from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

import tiktoken
from discord import Message, Reaction
from discord.ext.commands import Context
from loguru import logger
from openai import OpenAI

from iqbot.config import settings

client = OpenAI(api_key=settings.tokens.gpt)


def count_tokens(input: str) -> int:
    encoding = tiktoken.encoding_for_model(settings.gpt.model)
    return len(encoding.encode(input))


def available_tokens(input: str) -> int:
    return (
        settings.gpt.tokens.limit
        - settings.gpt.tokens.overhead_max
        - settings.gpt.tokens.prompt_max
        - settings.gpt.tokens.output_max
        - count_tokens(input)
    )


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


def format_message(message: Message) -> str:
    reply_id = None
    if (
        message.reference
        and message.reference.resolved
        and isinstance(message.reference.resolved, Message)
    ):
        reply_id = message.reference.resolved.id
    id = message.id
    author = message.author.name
    if not reply_id:
        return f"[ID: {id} | {author}]: {message.content}"
    else:
        return f"[ID: {id} | {author} replying to {reply_id}]: {message.content}"


async def read_current_context(ctx: Context) -> str:
    messages = []
    context_tokens = available_tokens("")
    async for message in ctx.channel.history(
        before=datetime.now(),
        after=datetime.now() - timedelta(minutes=settings.gpt.history.minutes),
        limit=settings.gpt.history.messages,
        oldest_first=False,
    ):
        if message.author.bot:
            continue

        formatted_message = format_message(message)
        message_tokens = count_tokens(formatted_message)

        if context_tokens - message_tokens < 0:
            logger.warning("Not enough tokens available for the message.")
            break

        context_tokens -= message_tokens
        messages.append(formatted_message)

    return "\n".join(messages[::-1])


async def read_reaction_context(reaction: Reaction) -> str:
    messages = []
    context_tokens = available_tokens("")
    async for message in reaction.message.channel.history(
        before=reaction.message.created_at,
        after=reaction.message.created_at
        - timedelta(minutes=settings.gpt.history.minutes),
        limit=settings.gpt.history.messages,
        oldest_first=False,
    ):
        if message.author.bot:
            continue

        formatted_message = format_message(message)
        message_tokens = count_tokens(formatted_message)

        if context_tokens - message_tokens < 0:
            logger.warning("Not enough tokens available for the message.")
            break

        context_tokens -= message_tokens
        messages.append(formatted_message)

    return "\n".join(messages[::-1])


async def build_prompt(conversation: str, command_prompt: str) -> list[ChatMessage]:
    assert count_tokens(command_prompt) < 100
    messages = [
        ChatMessage(
            role=Role.SYSTEM,
            content=settings.gpt.system_prompt.strip(),
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
            max_tokens=settings.gpt.tokens.output_max,
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


if __name__ == "__main__":
    logger.info(f"System prompt length:{count_tokens(settings.gpt.system_prompt)}")
    logger.info(f"Max output tokens: {settings.gpt.tokens.output_max}")
