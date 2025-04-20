from datetime import timedelta
from enum import Enum
from typing import Optional

from discord import Message
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


async def read_context(ctx: Context) -> str:
    messages = []
    async for message in ctx.channel.history(
        before=ctx.message.created_at,
        after=ctx.message.created_at - timedelta(minutes=settings.gpt.history.minutes),
        limit=settings.gpt.history.messages,
    ):
        messages.append(f"{message.author.name}: {message.content}")
    return "\n".join(messages[::-1])


async def build_prompt(conversation: str, command_prompt: str) -> list[ChatMessage]:
    messages = [
        ChatMessage(
            role=Role.SYSTEM,
            content="You are a chat bot that answers questions based on the context of provided conversation. "
            "You are not allowed to answer any questions that are not related to the provided conversation. "
            "You should refer to users with the exact unicode characters provided in the conversation. "
            "When asked for a winner you should respond with the name of the winner as the first word of your response. "
            "You should assess the winner based on the logic and correctness of the arguments presented in the conversation. "
            f"Please limit your responses to {settings.gpt.max_tokens} tokens.",
        ),
        ChatMessage(
            role=Role.USER,
            content=f"Based on the following conversation: \n\n{conversation}\n\n please answer: {command_prompt}.",
        ),
    ]
    return messages


async def send_prompt(ctx: Context, command_prompt: str) -> str:
    conversation = await read_context(ctx)
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
