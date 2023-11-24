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


logging.basicConfig(filename="highroller.log", encoding="utf-8", level=logging.INFO, format='%(levelname)s:%(asctime)s:%(message)s', datefmt='%Y-%m-%d-%H-%M-%S')

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
    def __init__(self, id: int, messageId: Optional[int], bet: int, authorId: int, acceptedBy: Optional[int], state: ChallengeState | int, timeout: Optional[int], map: str, tribe: str, notes: str, gameName: Optional[str], winner: Optional[int]) -> None:
        self.id: int = id
        self.messageId: Optional[int] = messageId
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
        challenge = Challenge(id = db.getNewIdForChallenge(), messageId=None, bet=bet, authorId=authorId, acceptedBy=None, state=ChallengeState.PRECREATED, timeout=int(time.time() + lastsForMinutes*60), map=map, tribe=tribe, notes=notes, gameName=None, winner=None)
        return challenge

    @staticmethod
    def getById(id: int) -> Optional[Challenge]:
        """
        Returns challenge with given id from db, or None if there is no match.
        """
        challengeData = db.getChallengeById(id)
        if challengeData == None:
            return None
        else:
            return Challenge(*challengeData)

    @staticmethod
    def getByMessageId(messageId: int) -> Optional[Challenge]:
        """
        Returns challenge with given messageId from db, or None if there is no match.
        """
        challengeData = db.getChallengeByMessageId(messageId)
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

    def finishCreating(self, messageId: int | None) -> None:
        if self.state != ChallengeState.PRECREATED:
            raise ValueError("can't create a challange that's already created!")
        self.messageId = messageId
        self.state = ChallengeState.CREATED
        db.adjustPlayerChips(self.authorId, -self.bet)
        db.createChallenge(challangeId=self.id, messageId=self.messageId, bet=self.bet, authorId=self.authorId, acceptedBy=self.acceptedBy, state=self.state, timeout=self.timeout, map=self.map, tribe=self.tribe, notes=self.notes, gameName=self.gameName, winner=self.winner)
        
    def accept(self, playerId: int) -> None:
        """
        Make given player accept this challange
        """
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
        """
        Make given player confirm this challange
        """
        if playerId != self.authorId:
            raise ValueError("You can't confirm a game you're not hosting!")
        
        if self.state != ChallengeState.ACCEPTED:
            raise ValueError("The game is not waiting for confirmation!")
        
        db.setChallengeState(self.id, ChallengeState.CONFIRMED)
        self.state = ChallengeState.CONFIRMED

    def start(self, playerId: int, gameName: str) -> None:
        """
        Make given player start this challange with given name
        """
        if playerId != self.authorId:
            raise ValueError("You can't start a game you're not hosting!")
        
        if self.state != ChallengeState.CONFIRMED:
            raise ValueError("The game can't be started!")
        
        db.setChallengeName(self.id, gameName)
        self.gameName = gameName

        db.setChallengeState(self.id, ChallengeState.STARTED)
        self.state = ChallengeState.STARTED

    def claimVictory(self, winnerId: int) -> None:
        """
        Make given player claim the victory of this challange
        """
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
        """
        Make given player abort this challange.

        if byPlayer is None, the system is assumed to have aborted the challange
        """
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

    async def _DM (self, player: Player|None, message: str):
        if player != None:
            await cast(Player, player).DM(message=message)

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
        await self._DM(player=Player.getById(challenge.authorId), message=message)

    async def _sendAway(self, challenge: Challenge, message: str) -> None:
        """
        Send the away player of a given challange (if exists) a DM with given message.
        """
        await self._DM(player=Player.getById(challenge.acceptedBy), message=message)

    async def _deleteChallengeMessage(self, challenge: Challenge) -> None:
        if challenge.messageId:
            message = await self.messageChannel.fetch_message(cast(int, challenge.messageId))
            self.messages.discard(challenge.messageId)
            await message.delete()

    async def loadAllChallengesAfterRestart(self) -> None:
        for challange in Challenge.getAllChallengesByState(state=ChallengeState.CREATED):
            if challange.messageId != None:
                self.messages.add(cast(int,challange.messageId))
            logging.info("Loaded a challenge after restart!")

    async def createChallengeEntry(self, challenge: Challenge, private: bool) -> None:
        """
        Creates the message entry for given challange. Then finishes creating the challange.

        if private is true, no message will be generated.
        """
        logging.info(f"Created challenge: {str(challenge)} (private: {private})")
        if not private:
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
            await self._sendHost(challenge, f"{await challenge.toTextForMessages()} has been created")
            self.messages.add(cast(int, message.id))
            await message.add_reaction(ABORT_EMOJI)
            await message.add_reaction(ACCEPT_EMOJI)
            challenge.finishCreating(message.id)
        else:
            await self._sendHost(challenge, f"{await challenge.toTextForMessages()} has been created.")
            await self._sendHost(challenge, f"The challange is private, so it won't show up in listings."\
                "If you want someone to connect, they have to DM me the following command:\n"\
                "accept {challenge.id}")
            challenge.finishCreating(None)
    
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


    async def playerRegistered(self, playerId: int) -> None:
        await self._DM(Player.getById(playerId), "You have registered to Highroller tournament! Good luck have fun :D")

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
    
    async def _accept_challenge(self, challenge: Challenge, player: Player) -> None:
        challenge.accept(player.id)
        await bot.messenger.acceptChallenge(challenge)

    async def _abort_challenge(self, challenge: Challenge, player: Player) -> None:
        challenge.abort(player.id)
        await bot.messenger.abortChallenge(challenge)

    async def _confirm_challenge(self, challenge: Challenge, player: Player) -> None:
        challenge.confirm(player.id)
        await bot.messenger.confirmChallenge(challenge)

    async def _start_challenge(self, challenge: Challenge, player: Player, name: str) -> None:
        challenge.start(player.id, name)
        await bot.messenger.startChallenge(challenge)

    async def _claim_challenge(self, challenge: Challenge, player: Player) -> None:
        challenge.claimVictory(player.id)
        await bot.messenger.claimChallenge(challenge)

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
            player = Player.getById(message.author.id)
            if player == None:
                logging.info("player not recognized")
                raise ValueError("I don't recognize you! Please register using /register!")
            
            # just for typechecker
            player = cast(Player, player)

            args = message.content.strip().split(" ")

            # shouldn't really happen, but just in case
            if len(args) == 0:
                logging.info("no args recieved")
                raise ValueError("invalid number of arguments!")

            match args[0]:
                case "help":
                    await message.reply(HELPMESSAGE)


                case "create":
                    await message.reply("Please use the /create_command instead :)")

                
                case "abort":
                    if len(args) != 2:
                        raise ValueError("invalid number of arguments!")
                    
                    await self._abort_challenge(challenge=self._load_challenge(args[1]), player=player)


                case "accept":
                    if len(args) != 2:
                        raise ValueError("invalid number of arguments!")
                    
                    await self._accept_challenge(challenge=self._load_challenge(args[1]), player = player)


                case "confirm":
                    if len(args) != 2:
                        raise ValueError("invalid number of arguments!")
                    
                    await self._confirm_challenge(challenge=self._load_challenge(args[1]), player = player)


                case "start":
                    if len(args) <= 2:
                        raise ValueError("invalid number of arguments!")
                    
                    # game name can have multiple words, so we will do a bit of hacking :D
                    await self._start_challenge(challenge=self._load_challenge(args[1]), player = player, name=" ".join(args[2:]))


                case "win":
                    if len(args) != 2:
                        raise ValueError("invalid number of arguments!")
                    
                    await self._claim_challenge(challenge=self._load_challenge(args[1]), player = player)


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
        
        # reaction is valid
        try:
            player = Player.getById(payload.user_id)
            if player == None:
                raise ValueError("Player not registered!")
            player = cast(Player, player)

            challenge = cast(Challenge, Challenge.getByMessageId(payload.message_id))

            logging.info(f"recieved emoji {payload.emoji}")
            logging.debug("Challange state {challenge.state}")

            if str(payload.emoji) == ACCEPT_EMOJI:
                logging.info("accepted reaction")
                await self._accept_challenge(challenge=challenge, player=player)

            elif str(payload.emoji) == ABORT_EMOJI:
                logging.info("aborted reaction")
                await self._abort_challenge(challenge=challenge, player=player)

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
@discord.option("map", str, choices = MAP_OPTIONS)
@discord.option("tribe", str, choices = TRIBE_OPTIONS)
@discord.option("timeout", int, required = False, min_value = 1, default = 60*12, description="Number of minutes before this challange will automatically abort. (default is 12*60)")
@discord.option("private", bool, required = False, default = False)
async def create_challenge(ctx: discord.ApplicationContext, bet, map, tribe, timeout, private):
    # you can use them as they were actual integers
    try:
        challenge = Challenge.precreate(bet = int(bet), authorId=ctx.author.id, map=map, tribe=tribe, lastsForMinutes=timeout)
        await bot.messenger.createChallengeEntry(challenge=challenge, private=private)
        await ctx.respond("Success!", ephemeral=True)
    except ValueError as e:
        await ctx.respond(str(e), ephemeral=True)

@bot.command(description="Register yourself into our super cool tournament!")
async def register(ctx: discord.ApplicationContext):
    try:
        Player.create(ctx.author.id)
        await bot.messenger.playerRegistered(ctx.author.id)
        await ctx.respond("Success!", ephemeral=True)
    except ValueError as e:
        await ctx.respond(str(e), ephemeral=True)

@bot.command(description="Checkout someone's current number of chips!")
@discord.option("user", discord.User, description = "The player who you want to check out! (default is you)", required = False, default = None)
async def chips(ctx: discord.ApplicationContext, user: discord.User):
    try:
        if user != None:
            player = Player.getById(user.id)
        else:
            player = Player.getById(ctx.author.id)

        if player != None:
            await ctx.respond("Success!", ephemeral=True)
            player = cast(Player, player)
            winrate = player.getGameScore()
            await ctx.channel.send(f"{await player.getName()} has {player.currentChips} chips! ({player.totalChips} across all periods)\Winrate is: {winrate[0]}/{winrate[1]}")
        else:
            await ctx.respond(f"Player isn't registered!", ephemeral=True)
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
        sys.exit()
    await ctx.respond("No Permissions")

bot.run(TOKEN)