DISCORD_MAX = 2000


def split_message(text: str, limit: int = DISCORD_MAX) -> list[str]:
    """Split text into chunks that fit within Discord's character limit,
    preferring to break at newlines."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break

        split_at = text.rfind("\n", 0, limit)
        if split_at <= 0:
            split_at = limit

        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")

    return chunks


async def send_long_response(ctx, text: str) -> None:
    """Send a potentially long AI response as a slash-command response,
    using ctx.respond for the first chunk and channel.send for the rest."""
    chunks = split_message(text)
    await ctx.respond(chunks[0])
    for chunk in chunks[1:]:
        await ctx.channel.send(chunk)


async def send_long_message(channel, text: str) -> None:
    """Send a potentially long message to a channel, splitting as needed."""
    for chunk in split_message(text):
        await channel.send(chunk)
