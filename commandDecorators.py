from __future__ import annotations
import discord

from typing import Any, Callable, Optional, Protocol, Awaitable
import functools

from constants import LIST_OF_ADMINS
from player import Player

replyFunction = Callable[[str], Awaitable[Any]]
WrappableFunction = Callable[[Any, list[str], discord.Member, replyFunction], Awaitable[None]]

def ensureRegistered(func: WrappableFunction) -> WrappableFunction:
    """
    ensures "author" is registered
    """
    @functools.wraps(func)
    def wrapper(self: Any, args: list[str], author: discord.Member, reply: replyFunction):
        if Player.getById(author.id) == None:
            raise ValueError("You need to register using \"register\" command!")
        return func(self, args, author, reply)
        
    return wrapper

def ensureAdmin(func: WrappableFunction) -> WrappableFunction:
    """
    ensures "author" is admin
    """
    @functools.wraps(func)
    def wrapper(self: Any, args: list[str], author: discord.Member, reply: replyFunction):
        if author.id not in LIST_OF_ADMINS:
            raise ValueError("You don't have the rights to use this command!")
        return func(self, args, author, reply)
        
    return wrapper

def ensureNumberOfArgumentsIsExactly(number: int):
    """
    ensures "args" has correct length
    """
    def decorator(func: WrappableFunction) -> WrappableFunction:
        @functools.wraps(func)
        def wrapper(self: Any, args: list[str], author: discord.Member, reply: replyFunction):
            if len(args) != number:
                raise ValueError("You need to register using \"register\" command!")
            return func(self, args, author, reply)
        
        return wrapper
    
    return decorator
        
def ensureNumberOfArgumentsIsAtLeast(number: int):
    """
    ensures "args" has correct length
    """
    def decorator(func: WrappableFunction) -> WrappableFunction:
        @functools.wraps(func)
        def wrapper(self: Any, args: list[str], author: discord.Member, reply: replyFunction):
            if len(args) >= number:
                raise ValueError("You need to register using \"register\" command!")
            return func(self, args, author, reply)
        
        return wrapper
    
    return decorator
        
def ensureNumberOfArgumentsIsAtMost(number: int):
    """
    ensures "args" has correct length
    """
    def decorator(func: WrappableFunction) -> WrappableFunction:
        @functools.wraps(func)
        def wrapper(self: Any, args: list[str], author: discord.Member, reply: replyFunction):
            if len(args) <= number:
                raise ValueError("You need to register using \"register\" command!")
            return func(self, args, author, reply)
        
        return wrapper
    
    return decorator
        