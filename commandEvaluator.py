from __future__ import annotations
from typing import Optional, cast, Callable, Any, Awaitable, Protocol
import logging
import functools

import discord
import logging

from messenger import Messenger
from challenge import Challenge
from player import Player
from accessDecorators import ensureAdmin, ensureRegistered, replyFunction
from constants import HELPMESSAGE, ChallengeState


async def emptyReply(message: str):
    pass

class CommandEvaluator:
    def __init__(self, messenger: Messenger, bot: discord.Bot):
        self.messenger = messenger
        self.bot = bot

    async def parseCommand(self, message: str, rawAuthor: discord.User | discord.Member | None, reply: replyFunction = emptyReply, source = None) -> bool:
        """
        parse a command and return if the command is valid
        """
        print("called command")
        print(message)
        author: Optional[discord.Member] = await self.bot.guild.fetch_member(rawAuthor.id) if rawAuthor != None else None # type: ignore

        try:
            args = message.strip().split(" ")
            await self.evaluateCommand(args=args, author=author, reply=reply)
            return True
        except ValueError as e:
            logging.warning(f"Error parsing command {f'from {source}' if source != None else ''}")
            logging.warning(str(e))
            await reply(str(e))
            return False

    async def evaluateCommand(self, args: list[str], author: discord.Member | None, reply: replyFunction = emptyReply) -> None:

        if author == None:
            raise ValueError("You are not a member of our guild!")
        author = cast(discord.Member, author)


        # shouldn't really happen, but just in case
        if len(args) == 0:
            logging.info("no args recieved")
            raise ValueError("invalid number of arguments!")

        # match commands
        match args[0]:
            case "register":
                await self.command_register([], author, reply)

            case "help":
                await self.command_help([], author, reply)

            case "list":
                await self.command_list(args[1:], author, reply)
            
            case "create":
                await self.command_create(args[1:], author, reply)

            case "abort":
                await self.command_abort(args[1:], author, reply)

            case "accept":
                await self.command_accept(args[1:], author, reply)

            case "start":
                await self.command_start(args[1:], author, reply)

            case "win":
                await self.command_win(args[1:], author, reply)

            case "forceabort":
                await self.command_force_abort(args[1:], author, reply)
            
            case "forcewin":
                await self.command_force_win(args[1:], author, reply)
                
            case _:
                raise ValueError("unknown command. Try \"help\" command.")

    async def command_help(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        await reply(HELPMESSAGE)

    async def command_register(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        Player.create(author.id)
        await reply("You have succesfully registered!")

    @ensureRegistered
    async def command_list(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
            list takes at least one argument which specifies which games to list

            argument options:
                "all", "done", "open", "playing", "mine", "aborted"
        """
        if len(args) < 1:
            raise ValueError("invalid number of arguments!")
        
        for arg in args[1:]:
            if arg not in ["all", "done", "open", "playing", "mine", "aborted"]:
                raise ValueError(f"invalid argument \"{arg}\"")
        done = open = inProgress = aborted = False
        withPlayers: list[int] = []

        # we will need to manipulate with i
        i = 0
        while i < len(args):
            arg = args[i]

            match arg:
                case "all":
                    done = open = inProgress = True

                case "done":
                    done = True

                case "open":
                    open = True

                case "playing":
                    inProgress = True

                case "aborted":
                    aborted = True

                case "mine":
                    withPlayers.append(author.id)

                case "with":
                    i += 1
                    if i >= len(args):
                        raise ValueError("After argument 'with' there should be a player ID")
                    withPlayers.append(self.parseId(args[i]))
            
            i += 1

        allChallenges: list[Challenge] = []

        if open:
            allChallenges += Challenge.getAllChallengesByState(state=ChallengeState.CREATED)

        if inProgress:
            for state in [ChallengeState.ACCEPTED, ChallengeState.STARTED]:
                allChallenges += Challenge.getAllChallengesByState(state=state)

        if done:
            allChallenges += Challenge.getAllChallengesByState(state=ChallengeState.FINISHED)

        if aborted:
            allChallenges += Challenge.getAllChallengesByState(state=ChallengeState.ABORTED)

        for playerId in withPlayers:
            allChallenges = [challenge for challenge in allChallenges if challenge.authorId == playerId or challenge.acceptedBy == playerId]

        await reply("\n\n".join([await challenge.toTextForMessages() for challenge in allChallenges]))
        return None

    @ensureRegistered
    async def command_create(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        await reply("Please use the /create_command instead :)")

    @ensureRegistered
    async def command_abort(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        if len(args) != 1:
            raise ValueError("invalid number of arguments!")
        
        challenge: Challenge = self.load_challenge(args[0])
        challenge.abort(byPlayer = author.id, force=False)
        await self.messenger.abortChallenge(challenge)

    @ensureRegistered
    async def command_accept(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        takes 1 argument:
            id of game to accept
        """
        if len(args) != 1:
            raise ValueError("invalid number of arguments!")
        
        challenge: Challenge = self.load_challenge(args[0])
        challenge.accept(playerId = author.id)
        await self.messenger.acceptChallenge(challenge)

    @ensureRegistered
    async def command_start(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        if len(args) <= 1:
            raise ValueError("invalid number of arguments!")
        
        challenge: Challenge = self.load_challenge(args[0])
        challenge.start(playerId = author.id, gameName=" ".join(args[1:]))
        await self.messenger.startChallenge(challenge)

    @ensureRegistered
    async def command_win(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        if len(args) != 1:
            raise ValueError("invalid number of arguments!")
        
        challenge: Challenge = self.load_challenge(args[0])
        challenge.claimVictory(winnerId = author.id, force=False)
        await self.messenger.claimChallenge(challenge)

    @ensureAdmin
    async def command_force_abort(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        if len(args) != 1:
            raise ValueError("invalid number of arguments!")
        
        challenge: Challenge = self.load_challenge(args[0])
        # if someone has already won before, we need to take away his win

        if challenge.winner != None:
            challenge.unwin()

        challenge.abort(byPlayer = author.id, force=True)
        await self.messenger.abortChallenge(challenge)

    @ensureAdmin
    async def command_force_win(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        if len(args) != 2:
            raise ValueError("invalid number of arguments!")

        if Player.getById(int(args[1])) == None:
            raise ValueError("Given player isn't registered!")
        
        challenge: Challenge = self.load_challenge(args[0])
        
        # if someone has already won before, we need to take away his win
        if challenge.winner != None:
            challenge.unwin()

        challenge.claimVictory(winnerId = int(args[2]), force=True)
        await self.messenger.claimChallenge(challenge)

    def load_challenge(self, challengeId: str) -> Challenge:
        """
        loads challenge by id string. If not found, throws ValueError
        """
        
        challenge = Challenge.getById(self.parseId(challengeId))

        if challenge == None:
            raise ValueError("The game doesn't exist!")
        
        return cast(Challenge, challenge)

    def parseId(self, id: str) -> int:
        """
        returns parsed id.

        Raises:
            ValueError - id isn't a number
        """
        try:
            return int(id)
        except ValueError:
            raise ValueError(f"ID '{id}' should be a number!")