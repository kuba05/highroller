from __future__ import annotations

from enum import Enum
import os
import json
import discord
from discord.ext import tasks
from dotenv import load_dotenv
from db import Database
import sys
import time
import datetime

from typing import Optional

STARTING_CHIPS=10

load_dotenv()
intents = discord.Intents.default()
intents.message_content = True

db = Database('db.db')

CLIENT_ID = os.getenv('CLIENT_ID')
TOKEN = os.getenv('TOKEN')
challengesChannelId = int(os.getenv('CHALLENGES'))
spamChannelId = int(os.getenv('SPAM'))



ACCEPT_EMOJI = "⚔"
ABORT_EMOJI = "❌"



HELPMESSAGE = f"""TODO
"""

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
    def getById(id: int) -> Optional[Player]:
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
            if not self.dmChannel:
                self.dmChannel = await member.create_dm()

            await self.dmChannel.send(message)
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
    def __init__(self, messageId: int, bet: int, authorId: int, acceptedBy: Optional[int], state: ChallengeState | int, timeout: Optional[int], notes: str, gameName: Optional[str], winner: Optional[int]) -> None:
        self.id: int = messageId
        self.bet: int = bet
        self.authorId: int = authorId
        self.acceptedBy: Optional[int] = acceptedBy
        if type(state) == type(1):
            state = ChallengeState(state)
        self.state: ChallengeState = state
        self.timeout: Optional[int] = timeout
        self.notes: str = notes
        self.gameName: Optional[str] = gameName
        self.winner: Optional[int] = winner
    
    def __str__(self):
        return f"Challenge {self.id} by {self.authorId}. State {self.state}. Bet {self.bet}. Timeout: {datetime.datetime.fromtimestamp(self.timeout)} Notes:\"{self.notes}\""
    
    @staticmethod
    def precreate(bet: int, authorId: int, lastsForMinutes = 60*24*355, notes = "") -> Challenge:
        """
        Creates a challenge object with no connection to database.

        To connect it to DB, call finishCreating method
        """
        author = Player.getById(authorId)
        if author == None:
            raise ValueError("You are not registered!")
        if author.currentChips < bet:
            raise ValueError("You don't have enough chips")

        challenge = Challenge(None, bet, authorId, None, ChallengeState.PRECREATED, int(time.time() + lastsForMinutes*60), notes, None, None)
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
        db.createChallenge(self.id, self.bet, self.authorId, self.acceptedBy, self.state.value, self.timeout, self.notes, self.gameName, self.winner)
        
    def accept(self, playerId: int) -> None:
        if self.state != ChallengeState.CREATED:
            raise ValueError("Challenge has already been accepted!")
        
        # TODO: disabled for testing
        #if self.authorId == playerId:
        #    raise ValueError("You can't accept your own challenge!")
        
        player = Player.getById(playerId)
        if player == None:
            raise ValueError("You are not registered!")
        if player.currentChips < self.bet:
            raise ValueError("You don't have enough chips")
        
        db.setChallengeState(self.id, ChallengeState.ACCEPTED)
        db.setChallengeAcceptedBy(self.id, playerId)
        db.adjustPlayerChips(playerId, - self.bet)

    def confirm(self, playerId: int) -> None:
        if playerId != self.authorId:
            raise ValueError("You can't confirm a game you're not hosting!")
        
        if self.state != ChallengeState.ACCEPTED:
            raise ValueError("The game is not waiting for confirmation!")
        
        db.setChallengeState(self.id, ChallengeState.CONFIRMED)
    
    def start(self, playerId: int, gameName: str) -> None:
        if playerId != self.authorId:
            raise ValueError("You can't start a game you're not hosting!")
        
        if self.state != ChallengeState.CONFIRMED:
            raise ValueError("The game can't be started!")
        
        db.setChallengeName(self.id, gameName)
        db.setChallengeState(self.id, ChallengeState.STARTED)

    def claimVictory(self, winnerId: int) -> None:
        if winnerId not in [self.authorId, self.acceptedBy]:
            raise ValueError("You can't finish a game you're not part of!")
        
        if self.state != ChallengeState.STARTED:
            raise ValueError("The game can't be finished!")
        
        db.setChallengeState(self.id, ChallengeState.FINISHED)
        db.setChallengeWinner(self.id, winnerId)
        db.adjustPlayerChips(winnerId, self.bet*2)

    def abort(self, byPlayer: int) -> None:
        if byPlayer not in [self.authorId, self.acceptedBy, None]:
            raise ValueError("You can't abort a game you're not part of!")
        
        if self.state not in [ChallengeState.CREATED, ChallengeState.ACCEPTED]:
            raise ValueError("Can't abort game that has already been started!")
        
        db.setChallengeState(self.id, ChallengeState.ABORTED)
        db.adjustPlayerChips(self.authorId, self.bet)

        if self.state == ChallengeState.ACCEPTED:
            db.adjustPlayerChips(self.acceptedBy, self.bet)
            db.increasePlayerAbortedCounter(byPlayer)


class Messenger:
    """
    Object to make sending messages easier.

    Should be created with create factory method.
    """
    messageChannel: discord.TextChannel
    messages: set[discord.Message]

    @staticmethod
    async def create(messageChannelId: int) -> Messenger:
        """
        Creates Messenger object and links messageChannel to it.
        """
        messenger = Messenger()
        messenger.messageChannel: discord.TextChannel = await bot.fetch_channel(messageChannelId)
        messenger.messages =  set()
        print(f"message channel: {messenger.messageChannel} (server: {messenger.messageChannel.guild})")
        return messenger

    async def _sendAll(self, challenge: Challenge, messages: list[str]) -> None:
        """
        Send all players associated with given challange DMs with given messages.
        """
        # use set to remove dublicities
        recipients = {i for i in (Player.getById(challenge.authorId), Player.getById(challenge.acceptedBy)) if i != None}
        for recipient in recipients:
            for message in messages:
                await recipient.DM(message)

    async def _deleteChallengeMessage(self, challenge: Challenge) -> None:
        message = await self.messageChannel.fetch_message(challenge.id)
        self.messages.discard(challenge.id)
        await message.delete()

    async def createChallengeEntry(self, challenge: Challenge) -> None:
        print(f"Created challenge: {str(challenge)}")
        message = await self.messageChannel.send(f"Challenge by {challenge.authorId}")
        challenge.finishCreating(message.id)
        self.messages.add(challenge.id)
        await message.add_reaction(ABORT_EMOJI)
        await message.add_reaction(ACCEPT_EMOJI)

    async def loadAllChallengesAfterRestart(self) -> None:
        for challange in Challenge.getAllChallengesByState(state=ChallengeState.CREATED):
            self.messages.add(challange.id)
            print("Loaded a challenge!")
    
    async def abortChallenge(self, challenge: Challenge) -> None:
        messages = [f"Challenge with ID {challenge.id} has been aborted."]
        await self._sendAll(challenge, messages)

        await self._deleteChallengeMessage(challenge)

        print("challenge aborted")

    async def abortChallengeDueTimeout(self, challenge: Challenge) -> None:
        messages = [f"Challenge with ID {challenge.id} has been aborted due timeout."]
        await self._sendAll(challenge, messages)

        await self._deleteChallengeMessage(challenge)

        print("challenge aborted due timeout")

    async def acceptChallenge(self, challenge: Challenge) -> None:
        messages = [f"Challenge with ID {challenge.id} has been accepted."]
        await self._sendAll(challenge, messages)

        await self._deleteChallengeMessage(challenge)

        print("challenge accepted")

    async def confirmChallenge(self, challenge: Challenge) -> None:
        messages = [f"Challenge with ID {challenge.id} has been confirmed.", f""]
        await self._sendAll(challenge, messages)
        print("challenge confirmed")

    async def startChallenge(self, challenge: Challenge) -> None:
        messages = [f"Challenge with ID {challenge.id} has been started."]
        await self._sendAll(challenge, messages)
        print("started")

    async def claimChallenge(self, challenge: Challenge) -> None:
        messages = [f"Challenge with ID {challenge.id} has been claimed."]
        await self._sendAll(challenge, messages)
        print("claimed confirmed")


class MyBot(discord.Bot):
    async def on_ready(self):
        print(f'Logged on as {self.user}!')
        print(f'guilds: {self.guilds}')
        self.messenger: Messenger = await Messenger.create(challengesChannelId)
        await self.messenger.loadAllChallengesAfterRestart()
        self.check_timeouts.start()

    async def on_message(self, message: discord.Message):
        if not isinstance(message.channel, discord.DMChannel):
            return
        
        if message.author.id == bot.user.id:
            print("it's me!")
            return
        
        print("recieved a DM!")
        user = Player.getById(message.author.id)
        if user == None:
            await message.reply("I don't recognize you! Please register!")
            return
        
        contents = message.content.split(" ")
        if len(contents) < 2 or not contents[0].isdigit():
            await message.reply("Invalid format! Your message should start with a game id followed by a command!")
            return
        
        challenge = Challenge.getById(int(contents[0]))
        if challenge == None:
            await message.reply("I don't recognize this game!")
            return 

        try:
            match contents[1]:
                case "abort":
                    challenge.abort(user.id)
                    await bot.messenger.abortChallenge(challenge)
                case "accept":
                    challenge.accept(user.id)
                    await bot.messenger.acceptChallenge(challenge)
                case "confirm":
                    challenge.confirm(user.id)
                    await bot.messenger.confirmChallenge(challenge)
                case "start":
                    if len(contents) < 3:
                        raise ValueError("start command requires one argument: game_name")
                    challenge.start(user.id, contents[2])
                    await bot.messenger.startChallenge(challenge)
                case "claim":
                    challenge.claimVictory(user.id)
                    await bot.messenger.claimChallenge(challenge)

        except ValueError as e:
            await message.reply(str(e))

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        print("reaction!")
        if payload.message_id not in self.messenger.messages or payload.event_type != "REACTION_ADD":
            print("not a recognized message!")
            return
        
        if payload.user_id == bot.user.id:
            print("my emoji!")
            return
        
        challenge = Challenge.getById(payload.message_id)
        print(payload.emoji)
        print(challenge.state)
        try:
            if str(payload.emoji) == ACCEPT_EMOJI:
                print("accepted")
                challenge.accept(payload.user_id)
                await bot.messenger.acceptChallenge(challenge)
            elif str(payload.emoji) == ABORT_EMOJI:
                print("aborted")
                challenge.abort(payload.user_id)
                await bot.messenger.abortChallenge(challenge)
            else:
                await self.get_message(payload.message_id).remove_reaction(payload.emoji, await bot.get_or_fetch_user(payload.user_id))
        except ValueError as e:
            print(str(e))
            await self.get_message(payload.message_id).remove_reaction(payload.emoji, await bot.get_or_fetch_user(payload.user_id))

    @tasks.loop(minutes=1)
    async def check_timeouts(self):
        print("checking for timeouts!")
        for challenge in Challenge.getNewTimeouts():
            try:
                challenge.abort(None)
                self.messenger.abortChallengeDueTimeout(challenge)
            except ValueError as e:
                print(e)


bot = MyBot()

@bot.command(description="Create a new challenge for the Highroller tournament!")
@discord.option("bet", int, min_value = 1)
async def create_challenge(ctx: discord.ApplicationContext, bet):
    # you can use them as they were actual integers
    try:
        challenge = Challenge.precreate(int(bet), ctx.author.id)
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
            winrate = player.getGameScore()
            await ctx.respond(f"You have {player.currentChips} chips! ({player.totalChips} across all periods)\nYour winrate is: {winrate[0]}/{winrate[1]}", ephemeral=True)
        else:
            await ctx.respond(f"Please register!", ephemeral=True)
    except ValueError as e:
        await ctx.respond(str(e), ephemeral=True)

@bot.command(description="Give yourself 10 chips so you can keep messing around!")
async def add_chips(ctx: discord.ApplicationContext):
    try:
        player = Player.getById(ctx.author.id)
        if player != None:
            player.adjustChips(10)
            await ctx.respond(f"Success!", ephemeral=True)
        else:
            await ctx.respond(f"Please register!", ephemeral=True)
    except ValueError as e:
        await ctx.respond(str(e))

@bot.command(description="List the top 10 players")
async def leaderboards(ctx: discord.ApplicationContext):
    await ctx.respond("OK", ephemeral=True)
    await ctx.channel.send(f"The top 10 players so far this run are:")
    player: Player
    for i, player in enumerate(Player.getTopPlayersThisSeason(10)):
        winrate = player.getGameScore()
        await ctx.channel.send(f"{i+1}. {await player.getName()} with {player.currentChips} chips")
        
    await ctx.channel.send(f"The top 10 players all times are:")
    for i, player in enumerate(Player.getTopPlayersAllTime(10)):
        winrate = player.getGameScore()
        await ctx.channel.send(f"{i+1}. {await player.getName()} {player.totalChips}")


bot.run(TOKEN)
sys.exit()