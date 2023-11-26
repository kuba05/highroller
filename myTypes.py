from typing import Callable, Awaitable, Any
import discord


class botWithGuild(discord.Bot): guild: discord.Guild


replyFunction = Callable[[str], Awaitable[Any]]
CommandFunction = Callable[[Any, list[str], discord.Member, replyFunction], Awaitable[None]]
