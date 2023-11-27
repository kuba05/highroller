from __future__ import annotations
import discord

from typing import Any, Callable, Optional, Protocol, Awaitable, cast, Iterable
import functools

from constants import LIST_OF_ADMINS
from player import Player
from myTypes import replyFunction, botWithGuild, CommandFunction

__MAX_ARGUMENTS = 256

# list of all registered commands
__registeredCommands: dict[str, CommandFunction] = {}

# number of arguments of registered commands
__argumentsOfCommands: dict[str, tuple[int, int]] = {}

# required access level for registered commands
__requiredAccessOfCommands: dict[str, str] = {}

# names of arguments of registered commands
__argumentNamesOfCommands: dict[str, str] = {}

# docstring of commands before they were tempered with
__rawDocsOfCommands: dict[str, str] = {}


def getAllRegisteredCommands() -> dict[str, CommandFunction]:
    """
    returns iterable over all registered commands
    """
    return __registeredCommands


def getHelpOfAllCommands() -> str:
    """
    return help message for all registered commands
    """
    messages = {}
    for value in set(__requiredAccessOfCommands.values()):
        messages[value] = "\n".join([cast(str, command.__doc__) for name, command in __registeredCommands.items() if __requiredAccessOfCommands[name] == value and name in __rawDocsOfCommands])

    return "\n\n".join([f"## Commands for {value}\n{messages[value]}" for value in messages])
        
    return "\n".join([cast(str, command.__doc__) for command in __registeredCommands.values() if command.__doc__ != None])



"""
    HELPERS
"""

def __getName(func: CommandFunction) -> str:
    if func.__name__.startswith("command_"):
        return func.__name__[8:]
    else:
        return func.__name__
    
def __trackNumberOfArguments(func: CommandFunction) -> CommandFunction:
    if __getName(func) not in __argumentsOfCommands:
        __argumentsOfCommands[__getName(func)] = (0, __MAX_ARGUMENTS)
    return func


def __concatArgumentsOfCommands(func: CommandFunction, newInterval: tuple[int, int]) -> None:
    __argumentsOfCommands[__getName(func)] = (max(__argumentsOfCommands[__getName(func)][0], newInterval[0]), min(__argumentsOfCommands[__getName(func)][1], newInterval[1]))
    if __argumentsOfCommands[__getName(func)][0] >__argumentsOfCommands[__getName(func)][0]:
        raise ValueError(f"No Valid number of arguments for {func.__name__}")


def __updateDocsForFunc(func: CommandFunction) -> None:
    if __getName(func) not in __rawDocsOfCommands:
        return

    func.__doc__ = f"{__getName(func)} " \
        f"{__argumentNamesOfCommands[__getName(func)] if __getName(func) in __argumentNamesOfCommands else ''} -{__rawDocsOfCommands[__getName(func)]} " 
    
def __updateRegisteredCommand(func: CommandFunction) -> None:
    if __getName(func) in __registeredCommands:
        __registeredCommands[__getName(func)] = func


"""
    DECORATORS
"""

def registerCommand(func: CommandFunction) -> CommandFunction:
    """
    adds the function to registeredCommands
    """
    __registeredCommands[__getName(func)] = func
    __trackNumberOfArguments(func)
    __updateDocsForFunc(func)
    if __getName(func) not in __requiredAccessOfCommands:
        __requiredAccessOfCommands[__getName(func)] = "everyone"

    return func

def autocompleteDocs(func: CommandFunction) -> CommandFunction:
    """
    adds information about arguments, access restrictions and command name to it's docstring
    """
    # remove leading whitespaces from all lines and adds one tab in front of each
    __rawDocsOfCommands[__getName(func)] = " ".join(line.strip() for line in cast(str, func.__doc__).split('\n')) if  func.__doc__ else ""
    __updateDocsForFunc(func)

    return func

def setArgumentNames(*args: str, **kwargs: str):
    def decorator(func):
        __argumentNamesOfCommands[__getName(func)] = " ".join([f'[{name}]' for name in args] + [f'[{name}] (default: {kwargs[name]})' for name in kwargs])

        __updateRegisteredCommand(func)
        __updateDocsForFunc(func)
        return func
    
    return decorator


"""
    ENSURERS
"""

def ensureRegistered(func: CommandFunction) -> CommandFunction:
    """
    ensures "author" is registered
    """

    @functools.wraps(func)
    def wrapper(self: Any, args: list[str], author: discord.Member, reply: replyFunction):
        if Player.getById(author.id) == None:
            raise ValueError("You need to register using \"register\" command!")
        return func(self, args, author, reply)

    __requiredAccessOfCommands[__getName(func)] = "registered"

    __updateRegisteredCommand(wrapper)
    __updateDocsForFunc(wrapper)
    return wrapper

def ensureAdmin(func: CommandFunction) -> CommandFunction:
    """
    ensures "author" is admin
    """
    @functools.wraps(func)
    def wrapper(self: Any, args: list[str], author: discord.Member, reply: replyFunction):
        if author.id not in LIST_OF_ADMINS:
            raise ValueError("You don't have the rights to use this command!")
        return func(self, args, author, reply)
        
    __requiredAccessOfCommands[__getName(func)] = "admin"

    __updateRegisteredCommand(wrapper)
    __updateDocsForFunc(wrapper)

    return wrapper

def ensureNumberOfArgumentsIsExactly(number: int):
    """
    ensures "args" has correct length
    """
    def decorator(func: CommandFunction) -> CommandFunction:
        
        @functools.wraps(func)
        def wrapper(self: Any, args: list[str], author: discord.Member, reply: replyFunction):
            if not (len(args) == number):
                raise ValueError(f"Wrong number of arguments! It should be exactly {number}.")
            return func(self, args, author, reply)

        __trackNumberOfArguments(func)
        __concatArgumentsOfCommands(func,(number, number))

        __updateRegisteredCommand(wrapper)
        __updateDocsForFunc(wrapper)

        return wrapper
    
            
    return decorator
        
def ensureNumberOfArgumentsIsAtLeast(number: int):
    """
    ensures "args" has correct length
    """
    def decorator(func: CommandFunction) -> CommandFunction:
        @functools.wraps(func)
        def wrapper(self: Any, args: list[str], author: discord.Member, reply: replyFunction):
            if not(len(args) >= number):
                raise ValueError(f"Wrong number of arguments! It should be at least {number}.")
            return func(self, args, author, reply)

        __trackNumberOfArguments(func)
        __concatArgumentsOfCommands(func,(number, __MAX_ARGUMENTS))

        __updateRegisteredCommand(wrapper)
        __updateDocsForFunc(wrapper)

        return wrapper
    
    return decorator
        
def ensureNumberOfArgumentsIsAtMost(number: int):
    """
    ensures "args" has correct length
    """
    def decorator(func: CommandFunction) -> CommandFunction:

        @functools.wraps(func)
        def wrapper(self: Any, args: list[str], author: discord.Member, reply: replyFunction):
            if not (len(args) <= number):
                print(number)
                print(args)
                raise ValueError(f"Wrong number of arguments! It should be at most {number}.")
            return func(self, args, author, reply)

        __trackNumberOfArguments(func)
        __concatArgumentsOfCommands(func,(0, number))

        __updateRegisteredCommand(wrapper)
        __updateDocsForFunc(wrapper)

        return wrapper
    
    return decorator