from __future__ import annotations

from enum import Enum
import os
import json
import discord
from dotenv import load_dotenv
from db import Database
import sys
import time

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



HELPMESSAGE = f"""
    Commands:
    /register - registeres you into the tournament
    /create_challenge - creates a challenge in <#{challengesChannelId}> for other players to accept
    /tokens - lists your current tokens

    Associated channels:
    <#{challengesChannelId}> - challenges are kept in this channel
    <#{spamChannelId}> - please use your commands in this channel

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
    def __init__(self, playerId: int, currentChips: int, totalChips: int, abortedGames: int):
        self.id = playerId
        self.currentChips = currentChips
        self.totalChips = totalChips
        self.abortedGames = abortedGames
        self.dmChannel = None

    @staticmethod
    def create(playerId: int) -> Player:
        if Player.getById(playerId) != None:
            raise ValueError("You are already registered!")

        player = Player(playerId, STARTING_CHIPS, STARTING_CHIPS, 0)
        db.createPlayer(player.id, player.currentChips, player.totalChips, player.abortedGames)
        return player

    @staticmethod
    def getById(id: int) -> Optional[Player]:
        playerData = db.getPlayer(id)
        if playerData == None:
            return None
        else:
            return Player(*playerData)
    
    async def DM(self, message: str) -> bool:
        member = await bot.fetch_user(self.id)
        try:
            if not self.dmChannel:
                self.dmChannel = await member.create_dm()

            await self.dmChannel.send(message)
        except discord.errors.Forbidden:
            return False
        return True
        
    def giveChips(self, number: int) -> None:
        if self.currentChips + number < 0:
            raise ValueError("You can't have negative chips!")
        db.adjustPlayerChips(self.id, number)
        self.currentChips += number
        self.totalChips += number
         
class Challenge:
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
        
    @staticmethod
    def precreate(bet: int, authorId: int, lastsForMinutes = 60*24*355, notes = "") -> Challenge:
        author = Player.getById(authorId)
        if author == None:
            raise ValueError("You are not registered!")
        if author.currentChips < bet:
            raise ValueError("You don't have enough chips")

        challenge = Challenge(None, bet, authorId, None, ChallengeState.PRECREATED, int(time.time() + lastsForMinutes*60), notes, None, None)
        return challenge

    @staticmethod
    def getById(id: int) -> Optional[Challenge]:
        challengeData = db.getChallenge(id)
        if challengeData == None:
            return None
        else:
            return Challenge(*challengeData)

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

    def claimVictory(self, playerId: int) -> None:
        if playerId not in [self.authorId, self.acceptedBy]:
            raise ValueError("You can't finish a game you're not part of!")
        
        if self.state != ChallengeState.STARTED:
            raise ValueError("The game can't be finished!")
        
        db.setChallengeState(self.id, ChallengeState.FINISHED)
        db.setChallengeWinner(self.id, playerId)
        db.adjustPlayerChips(playerId, self.bet*2)

    def abort(self, byPlayer: int) -> None:
        if byPlayer not in [self.authorId, self.acceptedBy]:
            raise ValueError("You can't abort a game you're not part of!")
        
        if self.state not in [ChallengeState.CREATED, ChallengeState.ACCEPTED]:
            raise ValueError("Can't abort game that has already been started!")
        
        db.setChallengeState(self.id, ChallengeState.ABORTED)
        db.adjustPlayerChips(self.authorId, self.bet)

        if self.state == ChallengeState.ACCEPTED:
            db.adjustPlayerChips(self.acceptedBy, self.bet)
            db.increasePlayerAbortedCounter(byPlayer)


class Messenger:
    messageChannel: discord.TextChannel
    messages: list[discord.Message]

    @staticmethod
    async def create(messageChannelId: int) -> Messenger:
        messenger = Messenger()
        messenger.messageChannel: discord.TextChannel = await bot.fetch_channel(messageChannelId)
        messenger.messages = []
        print(f"message channel: {messenger.messageChannel} (server: {messenger.messageChannel.guild})")
        return messenger

    async def _sendAll(self, challenge: Challenge, messages: list[str]) -> None:
        recipients = [i for i in (Player.getById(challenge.authorId), Player.getById(challenge.acceptedBy)) if i != None]
        for recipient in recipients:
            for message in messages:
                await recipient.DM(message)

    async def createChallengeEntry(self, challenge: Challenge) -> None:
        print(f"sending to {self.messageChannel}")
        message = await self.messageChannel.send(f"Challenge by {challenge.authorId}")
        challenge.finishCreating(message.id)
        self.messages.append(challenge.id)
        await message.add_reaction(ABORT_EMOJI)
        await message.add_reaction(ACCEPT_EMOJI)

    async def _deleteChallengeMessage(self, challenge) -> None:
        message = await self.messageChannel.fetch_message(challenge.id)
        await message.delete()

    async def abortChallenge(self, challenge: Challenge) -> None:
        messages = [f"Challenge with ID {challenge.id} has been aborted."]
        await self._sendAll(challenge, messages)

        await self._deleteChallengeMessage(challenge)

        print("challenge aborted")

    async def acceptChallenge(self, challenge: Challenge) -> None:
        messages = [f"Challenge with ID {challenge.id} has been accepted."]
        await self._sendAll(challenge, messages)

        await self._deleteChallengeMessage(challenge)

        print("challenge accepted")

    async def confirmChallenge(self, challenge: Challenge) -> None:
        messages = [f"Challenge with ID {challenge.id} has been accepted."]
        await self._sendAll(challenge, messages)
        print("challenge confirmed")

    async def startChallenge(self, challenge: Challenge) -> None:
        messages = [f"Challenge with ID {challenge.id} has been accepted."]
        await self._sendAll(challenge, messages)
        print("started confirmed")

    async def claimChallenge(self, challenge: Challenge) -> None:
        messages = [f"Challenge with ID {challenge.id} has been accepted."]
        await self._sendAll(challenge, messages)
        print("claimed confirmed")


class MyBot(discord.Bot):
    async def on_ready(self):
        print(f'Logged on as {self.user}!')
        print(f'guilds: {self.guilds}')
        self.messenger: Messenger = await Messenger.create(challengesChannelId)

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
        if payload.channel_id != challengesChannelId:
            print("wrong channel!")
            return
        
        challenge = Challenge.getById(payload.message_id)
        if challenge == None:
            print("not a real challange")
            return
        
        if payload.user_id == bot.user.id:
            print("my emoji!")
            return
        
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
                print('out')
        except ValueError as e:
            print(str(e))


bot = MyBot()

@bot.command(description="Create a new challenge for the Highroller tournament!")
@discord.option("bet", int, min_value = 1)
async def create_challenge(ctx: discord.ApplicationContext, bet):
    # you can use them as they were actual integers
    try:
        challenge = Challenge.precreate(int(bet), ctx.author.id)
        await bot.messenger.createChallengeEntry(challenge)
        await ctx.respond("Success!")
    except ValueError as e:
        await ctx.respond(str(e))

@bot.command(description="Register yourself into our super cool tournament!")
async def register(ctx: discord.ApplicationContext):
    try:
        Player.create(ctx.author.id)
        await ctx.respond("Success!")
    except ValueError as e:
        await ctx.respond(str(e))

@bot.command(description="Check your current number of chips!")
async def chips(ctx: discord.ApplicationContext):
    try:
        player = Player.getById(ctx.author.id)
        if player != None:
            await ctx.respond(f"You have {player.currentChips} chips! ({player.totalChips} across all periods)")
        else:
            await ctx.respond(f"Please register!")
    except ValueError as e:
        await ctx.respond(str(e))

@bot.command(description="Give yourself 10 chips so you can keep messing around!")
async def add_chips(ctx: discord.ApplicationContext):
    try:
        player = Player.getById(ctx.author.id)
        if player != None:
            player.giveChips(10)
            await ctx.respond(f"Success!")
        else:
            await ctx.respond(f"Please register!")
    except ValueError as e:
        await ctx.respond(str(e))


bot.run(TOKEN)
sys.exit()

@bot.event
async def on_ready():
    print("ready")
    print(f"invite link: https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&permissions=268512336&scope=bot%20applications.commands")

#@bot.event
async def on_message(message):
    print("recieved message", file=sys.stderr)
    
    if message.author == bot.user:
        return

    if message.channel.id == spamChannelId:
        try:
            print('deleting', file=sys.stderr)
            await message.delete()
        except:
            pass
            
    # DM
    if not message.guild:
        try:
            parts = message.content.split(" ")
            gameId = parts[0]
            challenge = db.getChallenge(gameId)
            if challenge == None:
                await message.channel.send("Game with this ID doesn't exist.")
                raise ValueError("Non-existing game")
            if message.author.id not in [challenge[2], challenge[3]]:
                await message.channel.send("You are not in this game.")
                raise ValueError("Not a member of the game")
            
            if parts[1] == "abort":
                if not await abortChallenge(challenge[0], message.author.id):
                    await message.channel.send("You can't abort this game. Perhaps it has already started?")
                    raise ValueError("can't abort the game")

                await message.channel.send("Game aborted.")
                
                if message.author.id == challenge[2]:
                    sendTo = challenge[3]
                else:
                    sendTo = challenge[2]

                await DM(sendTo, [f"Game {challenge[0]} has been aborted by your opponent :("])
                return

            if parts[1] == "start":
                if challenge[4] != 1:
                    await message.channel.send("This game has already started or been aborted!")
                    raise ValueError("game already started/aborted")

                if message.author.id != challenge[2]:
                    await message.channel.send("Only host can start the game!")
                    raise ValueError("Only host can start the game")

                try:
                    challenge = db.startChallenge(challenge[0], parts[2])
                except ValueError as e:
                    await message.channel.send(e)
                    raise e

                await message.channel.send(f"Game started. In game name is {challenge[7]}.")
                await message.channel.send("If you win the game, send me:")
                await message.channel.send(f"{challenge[0]} win")
                await DM(challenge[3], [f"Game started. In game name is {challenge[7]}.", "If you win the game, send me:", f"{challenge[0]} win"])
                return
            
            if parts[1] == "win":
                if challenge[4] != 2:
                    await message.channel.send("This game is not in progress!")
                    raise ValueError("game not in progress")
                try:
                    db.winChallenge(challenge[0], message.author.id == challenge[2])
                    x = "won" if message.author.id == challenge[2] else "lost"
                    await DM(challenge[2], [f"Game over!. You've {x}"])
                    x = "won" if message.author.id == challenge[3] else "lost"
                    await DM(challenge[3], [f"Game over!. You've {x}"])
                    print(f"game {challenge[0]} reported as win for {message.author.id}", file=sys.stderr)
                except ValueError as e:
                    await message.channel.send(e)
                    raise e



        except Exception as e:
            print(f"recieved invalid DM from {message.author}", file=sys.stderr)
            print(message.content, file=sys.stderr)
            print(e, file=sys.stderr, flush=True)



#@tasks.loop(minutes=1.0)
async def timeoutOldChallenges():
    print("checking timeouts", file=sys.stderr)
    currentTime = time.time()
    for challenge in db.getChallenges(status=0):
        if (challenge[5] <= currentTime):
            print("timeout", file=sys.stderr)
            await abortChallenge(challenge, challenge[2], True)


@bot.command(description="Create a new challenge for the Highroller tournament!")
async def create_challenge(ctx: discord.ApplicationContext, bet: int):
    """bet: discord.Option(int, description="number of chips you want to bet"),
    time: discord.Option(int, description="How many minutes do you want this challenge to last? You can always manually cancel the challenge."),
    notes: discord.Option(str, description="Any notes to be displayed with the challenge?")):"""
    await ctx.defer(ephemeral=True)
    try:
        challenge, message = await Challenge.precreate(bet, ctx.author.id, )
    except ValueError as e:
        await ctx.followup.send(str(e))
        return

    await ctx.followup.send("done")
    await setupReactions(ctx, challenge, message)
