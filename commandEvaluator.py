from __future__ import annotations
from typing import Optional, cast, Callable, Any, Awaitable, Protocol
import re

import discord
import logging

from messenger import Messenger
from challenge import Challenge
from player import Player
from commandDecorators import ensureAdmin, ensureRegistered, replyFunction, ensureNumberOfArgumentsIsAtLeast, ensureNumberOfArgumentsIsAtMost, ensureNumberOfArgumentsIsExactly, registerCommand, autocompleteDocs, getAllRegisteredCommands, getHelpOfAllCommands, setArgumentNames, disableIfFrozen
from constants import ChallengeState, HELPMESSAGE, TRIBE_OPTIONS, MAP_OPTIONS, TEAM_ROLES, CHALLENGES_LIST_CHANNEL
from myTypes import replyFunction, botWithGuild

async def emptyReply(message: str):
    pass

class CommandEvaluator:
    def __init__(self, messenger: Messenger, bot: botWithGuild):
        self.messenger = messenger
        self.bot = bot
        self.logFile = open("commandlog.log", "a")
        
        # max length of message is 2000 chars, so we will have to do a lot of hacking to keep lines intact :D
        self.helpMessage = []
        helpMessage = HELPMESSAGE + "\n\n" + getHelpOfAllCommands()

        while len(helpMessage) > 2000:
            lines = helpMessage[:2000].count("\n")
            a = helpMessage.split("\n", lines)
            self.helpMessage.append("\n".join(a[:-1]))
            helpMessage = a[-1]
        self.helpMessage.append(helpMessage)

        # when frozen is True, no new (nonforce) command are allowed - this will happen when there are technical difficulties and at the end of each split
        self.frozen = False
        self.__spliiter = re.compile("(\w+)|\"(.+?)\"|(\[.+?\])")


    async def parseCommand(self, message: str, rawAuthor: discord.User | discord.Member | None, reply: replyFunction = emptyReply, source = None) -> bool:
        """
        parse a command and return if the command is valid
        """

        author: Optional[discord.Member]

        if message[0] == "/":
            message = message[1:]
        if rawAuthor == None:
            author = None
        else:
            rawAuthor = cast(discord.User | discord.Member, rawAuthor)
            # fetching is potentially costly, so we don't want to fetch when not needed
            author =  self.bot.guild.get_member(rawAuthor.id)
            if author == None:
                author =  await self.bot.guild.fetch_member(rawAuthor.id)

        try:
            args = self.__spliiter.findall(message.strip())
            args = list(filter(lambda arg: arg!= "", map(lambda arg: "".join(arg).strip(), args)))
            await self.evaluateCommand(args=args, author=author, reply=reply, source=source)
            return True
        except ValueError as e:
            logging.warning(f"Error parsing command {f'from {source}' if source != None else ''}")
            logging.warning(str(e))
            await reply(str(e))
            return False

    async def evaluateCommand(self, args: list[str], author: discord.Member | None, reply: replyFunction = emptyReply, source = None) -> None:
        """
        runs a command with given args (first arg is command name)
        """

        if author == None:
            raise ValueError("You are not a member of our guild!")

        print(f"evaluating command from source: {source}; author: {cast(discord.Member, author).name}; args: {args}", file=self.logFile, flush=True)

        author = cast(discord.Member, author)


        # shouldn't really happen, but just in case
        if len(args) == 0:
            logging.info("no args recieved")
            raise ValueError("invalid number of arguments!")

        commandName = args[0].lower()

        # match commands
        if commandName not in getAllRegisteredCommands():
            raise ValueError("unknown command. Try \"help\" command.")
        
        await (getAllRegisteredCommands()[commandName](self, args[1:], author, reply))

    @autocompleteDocs
    @registerCommand
    @ensureNumberOfArgumentsIsExactly(0)
    async def command_help(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        display help message
        """
        await reply(HELPMESSAGE + f"""
                    
list of all commands:
{", ".join(getAllRegisteredCommands().keys())}""")

    @autocompleteDocs
    @registerCommand
    @ensureNumberOfArgumentsIsExactly(0)
    async def command_detailedhelp(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        display help message including description of all commands
        """
        for message in self.helpMessage:
            await reply(message)

    @autocompleteDocs
    @registerCommand
    @ensureNumberOfArgumentsIsExactly(0)
    async def command_register(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        register yourself to our amazing tournament!
        """
        Player.create(author.id)
        await self.messenger.playerRegistered(author.id)

    @autocompleteDocs
    @registerCommand
    @ensureNumberOfArgumentsIsAtLeast(1)
    async def command_list(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        lists all games which satisfy arguments.

        argument options:
            "all", "done", "open", "playing", "mine", "aborted", "from [player]"
        """
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
                    player = self.parsePlayer(args[i])
                    if player == None:
                        raise ValueError(f"Player {args[i]} doesn't exist!")
                    withPlayers.append(cast(Player, player).id)
            
                case _:
                    raise ValueError(f"not a recognized argument {arg} on position {i+1}")

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

        if len(allChallenges) == 0:
            await reply("no games match your options")
        else:
            await reply("\n\n".join([await challenge.toTextForMessages() for challenge in allChallenges]))




    @disableIfFrozen
    @autocompleteDocs
    @registerCommand
    @setArgumentNames("challenge", "message")
    @ensureRegistered
    @ensureNumberOfArgumentsIsExactly(2)
    async def command_send(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        sends all player in a game a message
        """
        challenge: Challenge = self.load_challenge(args[0])
        if author.id in [challenge.authorId, challenge.acceptedBy]:
            await self.messenger._sendAll(challenge, f"message from {author.display_name}:\n{args[1]}")
        else:
            raise ValueError("You are not part of the game!")


    @disableIfFrozen
    @autocompleteDocs
    @registerCommand
    @setArgumentNames("bet", "map", "tribe", timeout = "60*12", private = "False")
    @ensureRegistered
    @ensureNumberOfArgumentsIsAtLeast(3)
    @ensureNumberOfArgumentsIsAtMost(5)
    async def command_create(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        Creates a challenge. The challenge will be automatically abortded after [timeout] minutes. If the challenge is [private], it won't be listed in <#1170686597746917406>.
        """
        bet = int(args[0])
        map = args[1].lower()
        tribe = args[2].lower()

        if map not in MAP_OPTIONS:
            raise ValueError(f"Not a legal map type. I am sorry :( legal options are:\n{' '.join(MAP_OPTIONS)}")
        
        if tribe not in TRIBE_OPTIONS:
            raise ValueError(f"Not a legal tribe. I am sorry :(  legal options are:\n{' '.join(TRIBE_OPTIONS)}")
        
        if len(args) > 3:
            timeout = int(args[3])
        else:
            timeout = 60 * 12
        
        if len(args) > 4:
            if args[4].lower() not in ["true", "false"]:
                raise ValueError("Not a legal value for private. Should be True or False")

            private = (args[4].lower() == "true")

        
        challenge = Challenge.precreate(bet = int(bet), authorId=author.id, map=map, tribe=tribe, lastsForMinutes=timeout)
        await self.messenger.createChallengeEntry(challenge=challenge, private=private)

    
    @disableIfFrozen
    @autocompleteDocs
    @registerCommand
    @setArgumentNames("challenge")
    @ensureRegistered
    @ensureNumberOfArgumentsIsExactly(1)
    async def command_abort(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        abort challenge with given ID. Both players will be refunded their bet and the game will be canceled. Can only be used if the game hasn't been started yet. Abuse will be persecuted!
        """
        challenge: Challenge = self.load_challenge(args[0])
        challenge.abort(byPlayer = author.id, force=False)
        await self.messenger.abortChallenge(challenge)

    @disableIfFrozen
    @autocompleteDocs
    @setArgumentNames("challenge")
    @registerCommand
    @ensureRegistered
    @ensureNumberOfArgumentsIsExactly(1)
    async def command_accept(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        accepts challenge with given ID
        """
        challenge: Challenge = self.load_challenge(args[0])
        challenge.accept(playerId = author.id)
        await self.messenger.acceptChallenge(challenge)

    @disableIfFrozen
    @autocompleteDocs
    @setArgumentNames("challenge")
    @registerCommand
    @ensureRegistered
    @ensureNumberOfArgumentsIsAtLeast(2)
    async def command_start(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        starts challenge with given ID
        """
        challenge: Challenge = self.load_challenge(args[0])
        challenge.start(playerId = author.id, gameName=" ".join(args[1:]))
        await self.messenger.startChallenge(challenge)
        await reply("OK")

    @disableIfFrozen
    @autocompleteDocs
    @setArgumentNames("challenge")
    @registerCommand
    @ensureRegistered
    @ensureNumberOfArgumentsIsExactly(1)
    async def command_win(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        claims you have won challenge with given ID
        """
        challenge: Challenge = self.load_challenge(args[0])
        challenge.claimVictory(winnerId = author.id, force=False)
        await self.messenger.claimChallenge(challenge)

    @autocompleteDocs
    @setArgumentNames(player = "you")
    @registerCommand
    @ensureRegistered
    @ensureNumberOfArgumentsIsAtMost(1)
    async def command_userinfo(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        gives detailed information about player
        """
        if len(args) == 1:
            player = self.parsePlayer(args[0])
        else:
            player = Player.getById(author.id)

        if player == None:
            raise ValueError("Selected user doesn't exist!")
        
        player = cast(Player, player)

        winrate = player.getGameScore()
        message = f"{await player.getName()} has {player.currentChips} chips! ({player.totalChips} across all periods)\nWinrate is: {winrate[0]}/{winrate[1]}"
        
        await reply(message)

    @autocompleteDocs
    @registerCommand
    @ensureRegistered
    @ensureNumberOfArgumentsIsExactly(0)
    async def command_leaderboards(self, args: list[str], author: discord.Member, reply: replyFunction):
        """
        returns list of top 10 players this season and all time
        """
        message = f"""\
The top 10 players so far this run are:
""" + "\n".join([f'{i+1}. {await player.getName()} with {player.currentChips} chips' for i, player in enumerate(Player.getTopPlayersThisSeason(10))]) + """

The top 10 players all times are:
""" + "\n".join([f'{i+1}. {await player.getName()} with {player.currentChips} chips' for i, player in enumerate(Player.getTopPlayersAllTime(10))])
        
        await reply(message)
    
    @autocompleteDocs
    @registerCommand
    @setArgumentNames("challenge")
    @ensureRegistered
    @ensureNumberOfArgumentsIsExactly(1)
    async def command_gameinfo(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        return detailed information about challenge
        """
        challenge = self.load_challenge(args[0])
        message = f"""### Challenge {challenge.id}
by {await cast(Player, Player.getById(challenge.authorId)).getName()}
accepted by {await cast(Player, Player.getById(challenge.acceptedBy)).getName() if challenge.acceptedBy != None else 'TBD'}

Bet: {challenge.bet}
Map: {challenge.map}
Tribe: {challenge.tribe}
Timelimit: 24 hours

Gamename: {challenge.gameName}
Winner: {challenge.winner}

State: {challenge.state.name}
        """
        await reply(message)

        

        
    """
    ADMIN COMMANDS
    """
    @autocompleteDocs
    @registerCommand
    @setArgumentNames("challenge")
    @ensureAdmin
    @ensureNumberOfArgumentsIsExactly(1)
    async def command_forceabort(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        force abort challenge. This takes away winning from the winner
        """
        challenge: Challenge = self.load_challenge(args[0])
        # if someone has already won before, we need to take away his win

        if challenge.winner != None:
            challenge.unwin()

        challenge.abort(byPlayer = author.id, force=True)
        await self.messenger.abortChallenge(challenge)

    @autocompleteDocs
    @registerCommand
    @setArgumentNames("challenge", "winner")
    @ensureAdmin
    @ensureNumberOfArgumentsIsExactly(2)
    async def command_forcewin(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        force set winner of a challenge
        """
        player = self.parsePlayer(args[1])
        if player == None:
            raise ValueError("Given player isn't registered!")
        player = cast(Player, player)

        challenge: Challenge = self.load_challenge(args[0])
        
        # if someone has already won before, we need to take away his win
        if challenge.winner != None:
            challenge.unwin()

        challenge.claimVictory(winnerId = player.id, force=True)
        await self.messenger.claimChallenge(challenge)

    @autocompleteDocs
    @registerCommand
    @setArgumentNames("player", "chips")
    @ensureAdmin
    @ensureNumberOfArgumentsIsExactly(2)
    async def command_addchips(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        give a player some amount of chips (or take it away if chips is negative)
        """
        player = self.parsePlayer(args[0])

        if player == None:
            raise ValueError("Given player isn't registered!")
        
        player = cast(Player, player)

        amount = int(args[1])
        player.adjustChips(amount)

    @autocompleteDocs
    @registerCommand
    @ensureAdmin
    @ensureNumberOfArgumentsIsExactly(0)
    async def command_rankteams(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        create leaderboards by teams
        """
        points = {role: 0 for role in TEAM_ROLES}

        roleList: list[discord.Guild] = [cast(discord.Guild, i) for i in [self.bot.guild.get_role(roleId) for roleId in TEAM_ROLES] if i != None]
        for player in Player.getAll():
            member = self.bot.guild.get_member(player.id)
            if member == None:
                logging.error(f"Can't find member {player.id}")
                continue
            for role in roleList:
                if role in cast(discord.Member,member).roles:
                    points[role.id] += player.totalChips

        roleList.sort(key=lambda role: points[role.id], reverse=True)

        message = f"Top teams all time are:\n" + "\n".join([f'{i+1}. {team.name} --- {points[team.id]}' for i, team in enumerate(roleList)])
        await reply(message)

    """
    TECHNICAL COMMANDS
    """
    @registerCommand
    @ensureAdmin
    @ensureNumberOfArgumentsIsExactly(0)
    async def command_freeze(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        freezes "registered user" commands
        """
        self.frozen = True

    @registerCommand
    @ensureAdmin
    @ensureNumberOfArgumentsIsExactly(0)
    async def command_unfreeze(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        unfreezes "registered user" commands
        """
        self.frozen = False

    @registerCommand
    @ensureAdmin
    @ensureNumberOfArgumentsIsExactly(0)
    async def command_resetchips(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        reset all current season chips
        """
        Player.resetAllPlayersCurrentChips()

    @registerCommand
    @setArgumentNames("chips")
    @ensureAdmin
    @ensureNumberOfArgumentsIsExactly(1)
    async def command_giveeveryonemidroundchips(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        give all players some amount of chips (or take it away if chips is negative)
        """
        chips = int(args[0])

        Player.giveAllPlayersChips(chips)

    @registerCommand
    @ensureAdmin
    @ensureNumberOfArgumentsIsExactly(0)
    async def command_dumplogs(self, args: list[str], author: discord.Member, reply: replyFunction) -> None:
        """
        dumps all command logs
        """
        await author.send(file=discord.File(self.logFile.name))

    """
    HELPERS
    """
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
        
    def parsePlayer(self, idOrName: str) -> Optional[Player]:
        """
        returns user from discord.

        idOrName can either represend ID of the user, or their name in bot's guild
        """
        
        # it's number
        if idOrName.isdecimal():
            player = Player.getById(self.parseId(idOrName))
        
        # it's player name
        else:
            member = self.bot.guild.get_member_named(idOrName)
            print(member)
            player = Player.getById(cast(discord.Member, member).id) if member != None else None

        return player
