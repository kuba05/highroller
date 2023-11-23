from __future__ import annotations

from typing import cast, Optional

from enum import Enum
import os
import discord
from discord.ext import tasks
from dotenv import load_dotenv
import sys
import time
import datetime

import logging
from db import Database


logging.basicConfig(filename="highroller.log", encoding="utf-8", level=logging.DEBUG, format='%(levelname)s:%(asctime)s:%(message)s', datefmt='%Y-%m-%d-%H-%M-%S')

STARTING_CHIPS=10
SIZES = ["small", "normal", "large", "huge"]
SURFACES = ["drylands", "lakes", "continents"]
TRIBE_OPTIONS = ["Xin-xi", "Imperius", "Bardur", "Oumaji", "Kickoo", "Hoodrick", "Luxidoor", "Vengir", "Zebasi", "Ai-Mo", "Quetzali", "Yădakk", "Aquarion", "∑∫ỹriȱŋ", "Polaris", "Cymanti"]

MAP_OPTIONS = [size + " " + surface for size in SIZES for surface in SURFACES]


ACCEPT_EMOJI = "⚔"
ABORT_EMOJI = "❌"
HELPMESSAGE = f"""TODO"""





load_dotenv()
intents = discord.Intents.default()
intents.message_content = True

db = Database('db.db')

CLIENT_ID = os.getenv('CLIENT_ID')
TOKEN = os.getenv('TOKEN')


challengesChannelId = int(os.getenv('CHALLENGES')) # type: ignore
spamChannelId = int(os.getenv('SPAM')) # type: ignore



class ChallengeState(Enum):
    PRECREATED = 0
    CREATED = 1
    ACCEPTED = 2
    CONFIRMED = 3
    STARTED = 4
    FINISHED = 5
    ABORTED = 7


class Player:
    """
    Object to represent any player (discord user registered to this game).

    Should be created using factory methods: create, getById, getTopPlayersThisSeason, getTopPlayersAllTime
    """
    def __init__(self, playerId: int, currentChips: int, totalChips: int, abortedGames: int):
        self.id = playerId
        self.currentChips = currentChips
        self.totalChips = totalChips
        self.abortedGames = abortedGames
        self.dmChannel = None

    @staticmethod
    def create(playerId: int) -> Player:
        """
        Register a new player to the game. If player with same id already exists, ValueError is raised.
        """
        if Player.getById(playerId) != None:
            raise ValueError("You are already registered!")

        player = Player(playerId, STARTING_CHIPS, STARTING_CHIPS, 0)
        db.createPlayer(player.id, player.currentChips, player.totalChips, player.abortedGames)
        return player

    @staticmethod
    def getById(id: Optional[int]) -> Optional[Player]:
        """
        Returns player with given id from db, or None if there is no match.
        """
        playerData = db.getPlayer(id)
        if playerData == None:
            return None
        else:
            return Player(*playerData)
    
    @staticmethod
    def getTopPlayersThisSeason(count: int) -> list[Player]:
        return [Player(*playerData) for playerData in db.getTopPlayersThisEpoch(count)]
    
    @staticmethod
    def getTopPlayersAllTime(count: int) -> list[Player]:
        return [Player(*playerData) for playerData in db.getTopPlayersTotal(count)]
    
    async def DM(self, message: str) -> bool:
        """
        Send DM to the user. Returns if sending the message was successful.
        """
        member = await bot.fetch_user(self.id)
        try:
            await member.send(message)
        except discord.errors.Forbidden:
            return False
        return True
    
    async def getName(self) -> str:
        member = await bot.fetch_user(self.id)
        return member.name
        

    def adjustChips(self, number: int) -> None:
        if self.currentChips + number < 0:
            raise ValueError("You can't have negative chips!")
        db.adjustPlayerChips(self.id, number)
        self.currentChips += number
        self.totalChips += number
        
    def getGameScore(self) -> list[int]:
        wr = db.getPlayersWinrate(self.id)
        return [wr[0], wr[1]]

class Challenge:
    """
    Object to represent a challenge created by players.

    Should be constructed primarly by the following factory methods:
    - precreate
    - getById
    - getAllChallengesByState
    - getNewTimeouts
    """
    def __init__(self, messageId: int, bet: int, authorId: int, acceptedBy: Optional[int], state: ChallengeState | int, timeout: Optional[int], map: str, tribe: str, notes: str, gameName: Optional[str], winner: Optional[int]) -> None:
        self.id: int = messageId
        self.bet: int = bet
        self.authorId: int = authorId
        self.acceptedBy: Optional[int] = acceptedBy

        if type(state) == type(1):
            state = ChallengeState(state)
        state = cast(ChallengeState, state)
        self.state: ChallengeState = state

        self.timeout: Optional[int] = timeout
        self.map: str = map
        self.tribe: str = tribe
        self.notes: str = notes
        self.gameName: Optional[str] = gameName
        self.winner: Optional[int] = winner
    
    async def toTextForMessages(self):
        return f"Challenge {self.id} {await cast(Player, Player.getById(self.authorId)).getName()} vs {await cast(Player, Player.getById(self.acceptedBy)).getName() if self.acceptedBy else 'TBD'}"
        
    def __str__(self):
        return f"Challenge {self.id} by {self.authorId}. State {self.state}. Bet {self.bet}. Timeout: {datetime.datetime.fromtimestamp(self.timeout)} Notes:\"{self.notes}\""
    
    @staticmethod
    def precreate(bet: int, authorId: int, map:str, tribe: str, lastsForMinutes, notes = "") -> Challenge:
        """
        Creates a challenge object with no connection to database.

        To connect it to DB, call finishCreating method
        """
        author = Player.getById(authorId)
        if author == None:
            raise ValueError("You are not registered!")
        
        author = cast(Player, author)
        if author.currentChips < bet:
            raise ValueError("You don't have enough chips")

        # let's use a proxy value of -1 for id
        challenge = Challenge(messageId=-1, bet=bet, authorId=authorId, acceptedBy=None, state=ChallengeState.PRECREATED, timeout=int(time.time() + lastsForMinutes*60), map=map, tribe=tribe, notes=notes, gameName=None, winner=None)
        return challenge

    @staticmethod
    def getById(id: int) -> Optional[Challenge]:
        """
        Returns challenge with given id from db, or None if there is no match.
        """
        challengeData = db.getChallenge(id)
        if challengeData == None:
            return None
        else:
            return Challenge(*challengeData)

    @staticmethod
    def getAllChallengesByState(state: ChallengeState) -> list[Challenge]:
        """
        Returns a list of all challenges with matching state
        """
        return [Challenge(*challenge) for challenge in db.getChallengesByState(state)]

    @staticmethod
    def getNewTimeouts() -> list[Challenge]:
        """
        Returns a list of all challenges which should timeout
        """
        return [Challenge(*challenge) for challenge in db.getTimeoutedChallengesByStateAndTimeoutTime(ChallengeState.CREATED, int(time.time()))]

    def finishCreating(self, messageId: int) -> None:
        if self.state != ChallengeState.PRECREATED:
            raise ValueError("can't create a challange that's already created!")
        self.id = messageId
        self.state = ChallengeState.CREATED
        db.adjustPlayerChips(self.authorId, -self.bet)
        db.createChallenge(messageId=self.id, bet=self.bet, authorId=self.authorId, acceptedBy=self.acceptedBy, state=self.state, timeout=self.timeout, map=self.map, tribe=self.tribe, notes=self.notes, gameName=self.gameName, winner=self.winner)
        
    def accept(self, playerId: int) -> None:
        if self.state != ChallengeState.CREATED:
            raise ValueError("Challenge has already been accepted!")
        
        # TODO: disabled for testing
        #if self.authorId == playerId:
        #    raise ValueError("You can't accept your own challenge!")
        
        player = Player.getById(playerId)
        if player == None:
            raise ValueError("You are not registered!")
        player = cast(Player, player)
        if player.currentChips < self.bet:
            raise ValueError("You don't have enough chips")
        
        db.setChallengeState(self.id, ChallengeState.ACCEPTED)
        self.state = ChallengeState.ACCEPTED

        db.setChallengeAcceptedBy(self.id, playerId)
        self.acceptedBy = playerId

        db.adjustPlayerChips(playerId, - self.bet)

    def confirm(self, playerId: int) -> None:
        if playerId != self.authorId:
            raise ValueError("You can't confirm a game you're not hosting!")
        
        if self.state != ChallengeState.ACCEPTED:
            raise ValueError("The game is not waiting for confirmation!")
        
        db.setChallengeState(self.id, ChallengeState.CONFIRMED)
        self.state = ChallengeState.CONFIRMED

    def start(self, playerId: int, gameName: str) -> None:
        if playerId != self.authorId:
            raise ValueError("You can't start a game you're not hosting!")
        
        if self.state != ChallengeState.CONFIRMED:
            raise ValueError("The game can't be started!")
        
        db.setChallengeName(self.id, gameName)
        self.gameName = gameName

        db.setChallengeState(self.id, ChallengeState.STARTED)
        self.state = ChallengeState.STARTED

    def claimVictory(self, winnerId: int) -> None:
        if winnerId not in [self.authorId, self.acceptedBy]:
            raise ValueError("You can't finish a game you're not part of!")
        
        if self.state != ChallengeState.STARTED:
            raise ValueError("The game can't be finished!")
        
        db.setChallengeState(self.id, ChallengeState.FINISHED)
        self.state = ChallengeState.FINISHED

        db.setChallengeWinner(self.id, winnerId)
        self.winner = winnerId

        db.adjustPlayerChips(winnerId, self.bet*2)

    def abort(self, byPlayer: int) -> None:
        if byPlayer not in [self.authorId, self.acceptedBy, None]:
            raise ValueError("You can't abort a game you're not part of!")
        
        if self.state not in [ChallengeState.CREATED, ChallengeState.ACCEPTED]:
            raise ValueError("Can't abort game that has already been started!")
        
        db.setChallengeState(self.id, ChallengeState.ABORTED)
        db.adjustPlayerChips(self.authorId, self.bet)

        if self.state == ChallengeState.ACCEPTED:
            db.adjustPlayerChips(cast(int, self.acceptedBy), self.bet)
            db.increasePlayerAbortedCounter(byPlayer)


class Messenger:
    """
    Object to make sending messages easier.

    Should be created with create factory method.
    """
    messageChannel: discord.TextChannel
    messages: set[int]

    @staticmethod
    async def create(messageChannelId: int) -> Messenger:
        """
        Creates Messenger object and links messageChannel to it.
        """
        messenger = Messenger()

        messenger.messageChannel: discord.TextChannel = await bot.fetch_channel(messageChannelId) # type: ignore

        messenger.messages =  set()
        logging.debug(f"message channel: {messenger.messageChannel} (server: {messenger.messageChannel.guild})")
        return messenger

    async def _sendAll(self, challenge: Challenge, message: str) -> None:
        """
        Send all players associated with given challange DMs with given message.
        """
        await self._sendHost(challenge=challenge, message=message)
        await self._sendAway(challenge=challenge, message=message)

    async def _sendHost(self, challenge: Challenge, message: str) -> None:
        """
        Send the host of a given challange (if exists) a DM with given message.
        """
        if Player.getById(challenge.authorId) != None:
            await cast(Player, Player.getById(challenge.authorId)).DM(message)

    async def _sendAway(self, challenge: Challenge, message: str) -> None:
        """
        Send the away player of a given challange (if exists) a DM with given message.
        """
        if Player.getById(challenge.acceptedBy) != None:
            await cast(Player, Player.getById(challenge.acceptedBy)).DM(message)

    async def _deleteChallengeMessage(self, challenge: Challenge) -> None:
        message = await self.messageChannel.fetch_message(challenge.id)
        self.messages.discard(challenge.id)
        await message.delete()

    async def loadAllChallengesAfterRestart(self) -> None:
        for challange in Challenge.getAllChallengesByState(state=ChallengeState.CREATED):
            self.messages.add(challange.id)
            logging.info("Loaded a challenge after restart!")

    async def createChallengeEntry(self, challenge: Challenge) -> None:
        logging.info(f"Created challenge: {str(challenge)}")
        name = await Player.getById(challenge.authorId).getName() # type: ignore
        message = await self.messageChannel.send(
f"""
## ⚔️ {name} challanges you! ⚔️
bet: {challenge.bet}
map: {challenge.map}
tribe: {challenge.tribe}
timelimit: Live game

challange timeouts in <t:{challenge.timeout}:t>
"""
        )
        challenge.finishCreating(message.id)
        self.messages.add(challenge.id)
        await message.add_reaction(ABORT_EMOJI)
        await message.add_reaction(ACCEPT_EMOJI)
    
    async def abortChallenge(self, challenge: Challenge) -> None:
        await self._sendAll(challenge, f"{await challenge.toTextForMessages()} has been aborted.")
        await self._sendAll(challenge, "If you wish to create another one, use the /create_challenge command!")

        await self._deleteChallengeMessage(challenge)

        logging.info(f"challenge aborted {challenge.id}")

    async def abortChallengeDueTimeout(self, challenge: Challenge) -> None:
        await self._sendAll(challenge, f"{await challenge.toTextForMessages()} has been aborted due timeout.")
        await self._sendAll(challenge, "If you wish to create another one, use the /create_challenge command!")

        await self._deleteChallengeMessage(challenge)

        logging.info(f"challenge aborted due timeout {challenge.id}")

    async def acceptChallenge(self, challenge: Challenge) -> None:
        await self._deleteChallengeMessage(challenge)
        await self._sendAll(challenge, f"{await challenge.toTextForMessages()} has been accepted.")
        await self._sendAll(challenge, "Waiting for host to confirm he's ready")
        await self._sendHost(challenge, f"Please confirm you are ready by sending me the following command:\nconfirm {challenge.id}")

        logging.info(f"challenge accepted {challenge.id}")

    async def confirmChallenge(self, challenge: Challenge) -> None:
        await self._sendAll(challenge, f"{await challenge.toTextForMessages()} is ready to start!")
        await self._sendAll(challenge, "Waiting for the host to start it!")
        await self._sendHost(challenge, f"Please confirm you are ready by sending me the following command:\nstart {challenge.id} [gameName]")
        logging.info(f"challenge confirmed {challenge.id}")

    async def startChallenge(self, challenge: Challenge) -> None:
        await self._sendAll(challenge, f"{await challenge.toTextForMessages()} has been started! \nThe game name is {challenge.gameName}\n\nGLHF!")
        await self._sendAll(challenge, f"Once the game is over, the winner should send me the following command:\nwin {challenge.id} ")
        logging.info("started {challenge.id}")

    async def claimChallenge(self, challenge: Challenge) -> None:
        await self._sendAll(challenge, f"{await challenge.toTextForMessages()} has been claimed by {await cast(Player, Player.getById(challenge.winner)).getName()}! \nIf you want to dispute the claim, contact the mods!")
        logging.info("claimed {challenge.id}")


class MyBot(discord.Bot):
    async def on_ready(self: MyBot) -> None:
        print(f'Logged on as {self.user}!', file=sys.stderr)
        print(f'guilds: {self.guilds}', file=sys.stderr)
        self.messenger: Messenger = await Messenger.create(challengesChannelId)
        await self.messenger.loadAllChallengesAfterRestart()
        self.check_timeouts.start()

    def _load_challenge(self, idText: str) -> Challenge:
        if not idText[0].isdigit():
            raise ValueError("Invalid format! Your message should start with a game id followed by a command!")
        
        challenge = Challenge.getById(int(idText))
        if challenge == None:
            raise ValueError("I don't recognize this game!")
        
        return cast(Challenge, challenge)
        
    async def on_message(self, message: discord.Message):
        # if it's not a DM, ignore it
        if not isinstance(message.channel, discord.DMChannel):
            return
        
        if message.author.id == bot.user.id: # type: ignore
            # if it's from me, ignore it
            logging.debug("on_message thinks it's me!")
            return
        
        logging.info("recieved a DM!")

        # handle recieving a DM
        try:
            user = Player.getById(message.author.id)
            if user == None:
                logging.info("user not recognized")
                raise ValueError("I don't recognize you! Please register using /register!")
            
            # just for typechecker
            user = cast(Player, user)

            args = message.content.strip().split(" ")

            # shouldn't really happen, but just in case
            if len(args) == 0:
                logging.info("no args recieved")
                raise ValueError("invalid number of arguments!")

            match args[0]:
                case "help":
                    await message.reply(HELPMESSAGE)


                # abort the challenge
                case "abort":
                    if len(args) != 2:
                        raise ValueError("invalid number of arguments!")
                    
                    challenge = self._load_challenge(args[1])

                    challenge.abort(user.id)
                    await bot.messenger.abortChallenge(challenge)


                case "accept":
                    if len(args) != 2:
                        raise ValueError("invalid number of arguments!")
                    
                    challenge = self._load_challenge(args[1])

                    challenge.accept(user.id)
                    await bot.messenger.acceptChallenge(challenge)


                case "confirm":
                    if len(args) != 2:
                        raise ValueError("invalid number of arguments!")
                    
                    challenge = self._load_challenge(args[1])

                    challenge.confirm(user.id)
                    await bot.messenger.confirmChallenge(challenge)


                case "start":
                    if len(args) > 2:
                        raise ValueError("invalid number of arguments!")
                    
                    challenge = self._load_challenge(args[1])

                    # game name can have multiple words, so we will do a bit of hacking :D
                    challenge.start(user.id, " ".join(args[2:]))
                    await bot.messenger.startChallenge(challenge)


                case "win":
                    if len(args) != 2:
                        raise ValueError("invalid number of arguments!")
                    
                    challenge = self._load_challenge(args[1])

                    challenge.claimVictory(user.id)
                    await bot.messenger.claimChallenge(challenge)


                case _:
                    raise ValueError("unknown command. Try \"help\" command.")

        except ValueError as e:
            logging.warning("Error handling DM")
            logging.warning(str(e))
            await message.reply(str(e))

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.message_id not in self.messenger.messages or payload.event_type != "REACTION_ADD":
            logging.debug("reaction to an unrecognized message!")
            return
        
        if payload.user_id == bot.user.id: # type: ignore
            logging.debug("my emoji!")
            return
        
        challenge = cast(Challenge, Challenge.getById(payload.message_id))

        logging.info(f"recieved emoji {payload.emoji}")
        logging.debug("Challange state {challenge.state}")
        try:
            if str(payload.emoji) == ACCEPT_EMOJI:
                logging.info("accepted reaction")
                challenge.accept(payload.user_id)
                await bot.messenger.acceptChallenge(challenge)
            elif str(payload.emoji) == ABORT_EMOJI:
                logging.info("aborted reaction")
                challenge.abort(payload.user_id)
                await bot.messenger.abortChallenge(challenge)
            else:
                message = self.get_message(payload.message_id)
                if message != None:
                    await message.remove_reaction(payload.emoji, await bot.get_or_fetch_user(payload.user_id)) # type: ignore
        except ValueError as e:
            logging.warning("error handeling emoji")
            logging.warning(str(e))
            message = self.get_message(payload.message_id)
            if message != None:
                await message.remove_reaction(payload.emoji, await bot.get_or_fetch_user(payload.user_id)) # type: ignore

    @tasks.loop(minutes=1)
    async def check_timeouts(self):
        logging.info("checking for timeouts!")
        for challenge in Challenge.getNewTimeouts():
            try:
                logging.info(f"challange {challenge.id} aborted due to timeout")
                challenge.abort(None)
                await self.messenger.abortChallengeDueTimeout(challenge)
            except ValueError as e:
                logging.warning("error aborting challange due to timeout")
                logging.warning(e)


bot = MyBot()

@bot.command(description="Create a new challenge for the Highroller tournament!")
@discord.option("bet", int, min_value = 1)
@discord.option("map", str, choices=MAP_OPTIONS)
@discord.option("tribe", str, choices=TRIBE_OPTIONS)
@discord.option("timeout", int, required=False, min_value = 1, default = 60, description="Number of minutes before this challange will automatically abort. (default is 60)")
async def create_challenge(ctx: discord.ApplicationContext, bet, map, tribe, timeout):
    # you can use them as they were actual integers
    try:
        challenge = Challenge.precreate(bet = int(bet), authorId=ctx.author.id, map=map, tribe=tribe, lastsForMinutes=timeout)
        await bot.messenger.createChallengeEntry(challenge)
        await ctx.respond("Success!", ephemeral=True)
    except ValueError as e:
        await ctx.respond(str(e), ephemeral=True)

@bot.command(description="Register yourself into our super cool tournament!")
async def register(ctx: discord.ApplicationContext):
    try:
        Player.create(ctx.author.id)
        await ctx.respond("Success!", ephemeral=True)
    except ValueError as e:
        await ctx.respond(str(e), ephemeral=True)

@bot.command(description="Check your current number of chips!")
async def chips(ctx: discord.ApplicationContext):
    try:
        player = Player.getById(ctx.author.id)
        if player != None:
            await ctx.respond("Success!", ephemeral=True)
            player = cast(Player, player)
            winrate = player.getGameScore()
            await ctx.channel.send(f"You have {player.currentChips} chips! ({player.totalChips} across all periods)\nYour winrate is: {winrate[0]}/{winrate[1]}")
        else:
            await ctx.respond(f"Please register!", ephemeral=True)
    except ValueError as e:
        await ctx.respond(str(e), ephemeral=True)

@bot.command(description="Give yourself 10 chips so you can keep messing around!")
async def add_chips(ctx: discord.ApplicationContext):
    try:
        player = Player.getById(ctx.author.id)
        if player != None:
            player = cast(Player, player)
            player.adjustChips(10)
            await ctx.respond(f"Success!", ephemeral=True)
        else:
            await ctx.respond(f"Please register!", ephemeral=True)
    except ValueError as e:
        await ctx.respond(str(e))

@bot.command(description="List the top 10 players")
async def leaderboards(ctx: discord.ApplicationContext):
    await ctx.respond("Success!", ephemeral=True)
    await ctx.channel.send(f"The top 10 players so far this run are:")
    player: Player
    for i, player in enumerate(Player.getTopPlayersThisSeason(10)):
        winrate = player.getGameScore()
        await ctx.channel.send(f"{i+1}. {await player.getName()} with {player.currentChips} chips")
        
    await ctx.channel.send(f"The top 10 players all times are:")
    for i, player in enumerate(Player.getTopPlayersAllTime(10)):
        winrate = player.getGameScore()
        await ctx.channel.send(f"{i+1}. {await player.getName()} {player.totalChips}")

@bot.command(description="Checkout how to use this bot!")
async def help(ctx: discord.ApplicationContext):
    await ctx.respond("Success!")
    await ctx.channel.send(HELPMESSAGE)

@bot.command()
async def shutdown(ctx: discord.ApplicationContext):
    if await bot.is_owner(ctx.user):
        await ctx.respond("Exiting")
        print("exiting")
        exit()
    await ctx.respond("No Permissions")

bot.run(TOKEN)