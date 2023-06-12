import os
import json
import discord
from discord.commands import Option
from discord.ext import tasks
from dotenv import load_dotenv
from db import Database
import sys
import time



MOCK=True



load_dotenv()
intents = discord.Intents.default()
intents.message_content = True

db = Database('db.db', MOCK)

CLIENT_ID = os.getenv('CLIENT_ID')
TOKEN = os.getenv('TOKEN')
GUILD = json.loads(os.getenv('GUILDS'))
challengesChannelId = int(os.getenv('CHALLENGES'))
spamChannelId = int(os.getenv('SPAM'))

HELPMESSAGE = f"""
    Commands:
    /register - registeres you into the tournament
    /create_challenge - creates a challenge in <#{challengesChannelId}> for other players to accept
    /tokens - lists your current tokens

    Associated channels:
    <#{challengesChannelId}> - challenges are kept in this channel
    <#{spamChannelId}> - please use your commands in this channel

"""





bot = discord.Bot(intents=discord.Intents.all())

async def DM(memberId, messages):
    member = bot.get_guild(int(GUILD[0])).get_member(memberId)
    try:
        dmChannel = await member.create_dm()
        for message in messages:
            await dmChannel.send(message)
    except discord.errors.Forbidden:
        return False
    return True

async def createChallengeEntry(ctx, bet, lastsFor, notes):
    channel = await bot.fetch_channel(challengesChannelId)
    message = await channel.send(f"New challenge for {bet} chips")
    
    try:
        entry = db.createChallenge(messageId=message.id, bet=bet, authorId = ctx.author.id, lastForMinutes=lastsFor, notes=notes)
    except ValueError as e:
        await message.delete()
        raise e

    return entry, message

async def abortChallenge(challenge, byPlayerId, timeout=False):
    challengeMode = challenge[4]
    try:
        challenge = db.abortChallenge(challenge[0], byPlayerId)
    except ValueError as e:
        print(f"failed to abort challenge {challenge[0]} by {byPlayerId} because {e}", file=sys.stderr, flush=True)
        return False

    if challengeMode == 0:
        channel = bot.get_channel(challengesChannelId)
        message = await channel.fetch_message(challenge[0])
        try:
            await message.delete()
        except discord.NotFound:
            print("message not found", sys.stderr)
        if timeout:
            await DM(challenge[2], ["One of your challenges was aborted as noone responded to it in the given time frame."])
        return True
    
    elif challengeMode == 1:
        messageOne = f"The game {challenge[0]} was aborted." if not timeout else f"The game {challenge[0]} was aborted due to it not starting in the given time frame."
        await DM(challenge[2], [messageOne, "If the game has already started or there is any other problem, please contact a game director."])
        await DM(challenge[3], [messageOne, "If the game has already started or there is any other problem, please contact a game director."])
        return True
    
    return False

    

async def setupReactions(ctx, challenge, message):
    await message.add_reaction("⚔️")
    await message.add_reaction("❌")

    #TODO in case of performance difficulties, this can be boosted easily
    while True:
        reaction, user = await bot.wait_for("reaction_add", timeout=None)

        # reacted to a different message
        if reaction.message.id != challenge[0]:
            continue

        if challenge[4] == 0:
            if (MOCK or user.id != challenge[2]) and str(reaction.emoji) == "⚔️":
                try:
                    challenge = db.acceptChallenge(challenge[0], user.id)
                    await message.delete()
                    await prepareGame(ctx, challenge)
                    await message.delete()
                    break
                except ValueError as e:
                    print(f"failed to accept challenge {challenge[0]} by {user.id} because {e}", file=sys.stderr, flush=True)

            if user.id == challenge[2] and str(reaction.emoji) == "❌":
                if await abortChallenge(challenge, user.id): break

        await reaction.clear()

    print("accepted", file=sys.stderr)


async def prepareGame(ctx, challenge):
    host = ctx.guild.get_member(challenge[2])
    away = ctx.guild.get_member(challenge[3])
    print("preparing gane", file=sys.stderr)
    print(host, file=sys.stderr)
    print(away, file=sys.stderr)

    if (not await DM(challenge[2],
        [   
            f"Hi, your challenge has been accepted by {away.nick}/{away.name}. Please exchange friend requests and start the game by sending me:",
            f"{challenge[0]} start GameName",
            f"You can also abort it by sending me:",
            f"{challenge[0]} abort",
            f"Please don't abort unless neccecary tho :)"
        ])
    ):
        channel = await bot.fetch_channel(challengesChannelId)
        channel.send(f"Please enable your DMs! @[{challenge[2]}]")
        challenge = db.abortChallenge(challenge[0], challenge[2])
        if not await DM(challenge[3], [f"Your opponent doesn't have DMs enabled, so this game will be aborted :("]):
            channel.send(f"Please enable your DMs! @[{challenge[3]}]")
        return

    if (not await DM(challenge[3],
        [
            f" Hi, you have accepted {host.nick}/{host.name}'s challenge. He will send you friend request and the game shortly :)",
            "You can also abort this game by sending me:",
            f"{challenge[0]} abort",
            f"Please don't abort unless neccecary tho :)"
        ])
    ):
        channel = await bot.fetch_channel(challengesChannelId)
        channel.send(f"Please enable your DMs! @[{challenge[3]}]")
        challenge = db.abortChallenge(challenge[0], challenge[3])
        await DM(challenge[2], [f"Your opponent doesn't have DMs enabled, so this game will be aborted :("])



@bot.event
async def on_ready():
    print("ready")
    print(f"invite link: https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&permissions=268512336&scope=bot%20applications.commands")
    timeoutOldChallenges.start()

@bot.event
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



@tasks.loop(minutes=1.0)
async def timeoutOldChallenges():
    print("checking timeouts", file=sys.stderr)
    currentTime = time.time()
    for challenge in db.getChallenges(status=0):
        if (challenge[5] <= currentTime):
            print("timeout", file=sys.stderr)
            await abortChallenge(challenge, challenge[2], True)


# ****************
# *SLASH COMMANDS*
# ****************

@bot.slash_command(name="create_challenge", guild_ids=GUILD, description="Create a new challenge for the Highroller tournament!")
async def createChallenge(ctx, bet: Option(int, "number of chips you want to bet"), time: Option(int, "How many minutes do you want this challenge to last? You can always manually cancel the challenge."), notes: Option(str, "Any notes to be displayed with the challenge?")):
    await ctx.defer(ephemeral=True)
    try:
        challenge, message = await createChallengeEntry(ctx, bet, time, notes)
    except ValueError as e:
        await ctx.followup.send(str(e))
        return

    await ctx.followup.send("done")
    await setupReactions(ctx, challenge, message)

@bot.slash_command(name="register", guild_ids=GUILD, description="Register yourself into our super cool tournament!")
async def registerPlayer(ctx):
    await ctx.defer(ephemeral=True)
    try:
        player = db.createPlayer(ctx.author.id)
    except ValueError as e:
        await ctx.followup.send(str(e))
        return

    await ctx.followup.send("done")

@bot.slash_command(name="tokens", guild_ids=GUILD, description="Check the number of your tokens!")
async def tokens(ctx):
    await ctx.defer(ephemeral=True)
    player = db.getPlayer(ctx.author.id)
    if player == None:
        await ctx.followup.send("Player doesn't exist! Please register with /register command")
        return
    await ctx.followup.send(f"You have {player[1]} tokens this epoch. (Your total accross all epochs is {player[2]})")

@bot.slash_command(name="help", guild_ids=GUILD, description="Help with commands for the Highroller.")
async def help(ctx):
    await ctx.defer(ephemeral=True)
    await ctx.followup.send(HELPMESSAGE)



bot.run(TOKEN)
