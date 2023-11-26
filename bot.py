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
from constants import ChallengeState, HELPMESSAGE, MAP_OPTIONS, TRIBE_OPTIONS, GUILD_ID, ACCEPT_EMOJI, ABORT_EMOJI

# a bit of hacking to allow circular import
import challenge as challengeModule
import player as playerModule
import messenger as messengerModule
import myTypes


logging.basicConfig(filename="highroller.log", encoding="utf-8", level=logging.INFO, format='%(levelname)s:%(asctime)s:%(message)s', datefmt='%Y-%m-%d-%H-%M-%S')

load_dotenv()
intents = discord.Intents.all()

db = Database('db.db')

CLIENT_ID = os.getenv('CLIENT_ID')
TOKEN = os.getenv('TOKEN')


challengesChannelId = int(os.getenv('CHALLENGES')) # type: ignore
spamChannelId = int(os.getenv('SPAM')) # type: ignore



class MyBot(myTypes.botWithGuild):
    async def on_ready(self: MyBot) -> None:
        print(f'Logged on as {self.user}!', file=sys.stderr)
        print(f'guilds: {self.guilds}', file=sys.stderr)
        self.guild: discord.Guild = cast(discord.Guild, self.get_guild(GUILD_ID))

        # set everything up
        challengeModule.Challenge.setDb(db)
        playerModule.Player.setDb(db)
        playerModule.Player.setBot(self)
        self.messenger: messengerModule.Messenger = await messengerModule.Messenger.create(spamChannelId=spamChannelId, messageChannelId=challengesChannelId, bot=self)
        import commandEvaluator
        self.commandEvaluator = commandEvaluator.CommandEvaluator(self.messenger, self)

        await self.messenger.loadAllChallengesAfterRestart()
        self.check_timeouts.start()

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
        await self.commandEvaluator.parseCommand(message=message.content, rawAuthor=message.author, reply=message.reply, source="DM")


    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.message_id not in self.messenger.messages or payload.event_type != "REACTION_ADD":
            logging.debug("reaction to an unrecognized message!")
            return
        
        if payload.user_id == bot.user.id: # type: ignore
            logging.debug("my emoji!")
            return
        
        # reaction is valid
        challenge = cast(challengeModule.Challenge, challengeModule.Challenge.getByMessageId(payload.message_id))

        command = None

        logging.info(f"recieved emoji {payload.emoji}")
        logging.debug("Challange state {challenge.state}")

        if str(payload.emoji) == ACCEPT_EMOJI:
            logging.info("accepted reaction")
            command = f"accept {challenge.id}"

        elif str(payload.emoji) == ABORT_EMOJI:
            logging.info("aborted reaction")
            command = f"abort {challenge.id}"
        
        # either command wasn't set or the command isn't working
        if not (command != None and await self.commandEvaluator.parseCommand(cast(str,command), payload.member, source="reaction")):
            message = self.get_message(payload.message_id)

            # remove the message
            if message != None and payload.member != None:
                await message.remove_reaction(payload.emoji, payload.member) # type: ignore

                
        
    @tasks.loop(minutes=1)
    async def check_timeouts(self):
        logging.info("checking for timeouts!")
        for challenge in challengeModule.Challenge.getNewTimeouts():
            try:
                logging.info(f"challange {challenge.id} aborted due to timeout")
                await self.commandEvaluator.parseCommand(f"forceabort {challenge.id}", bot.user, source="timeout")
            except ValueError as e:
                logging.warning("error aborting challange due to timeout")
                logging.warning(e)


bot = MyBot(intents=intents)

async def parseCommandForAndSendSomething(ctx: discord.ApplicationContext, command:str, rawAuthor: discord.User, reply: myTypes.replyFunction) -> None:
    #await ctx.defer()
    if await bot.commandEvaluator.parseCommand(command, rawAuthor=rawAuthor, reply=reply):
        await ctx.respond("OK", ephemeral=True)


"""
SLASH COMMANDS
"""

@bot.command(description="Create a new challenge for the Highroller tournament!")
@discord.option("bet", int, min_value = 1)
@discord.option("map", str, choices = MAP_OPTIONS)
@discord.option("tribe", str, choices = TRIBE_OPTIONS)
@discord.option("timeout", int, required = False, min_value = 1, default = 60*12, description="Number of minutes before this challange will automatically abort. (default is 12*60)")
@discord.option("private", bool, required = False, default = False)
async def create_challenge(ctx: discord.ApplicationContext, bet, map, tribe, timeout, private):
    # you can use them as they were actual integers
    try:
        challenge = challengeModule.Challenge.precreate(bet = int(bet), authorId=ctx.author.id, map=map, tribe=tribe, lastsForMinutes=timeout)
        await bot.messenger.createChallengeEntry(challenge=challenge, private=private)
        await ctx.respond("Success!", ephemeral=True)
    except ValueError as e:
        await ctx.respond(str(e), ephemeral=True)

@bot.command(description="Register yourself into our super cool tournament!")
async def register(ctx: discord.ApplicationContext):
    await parseCommandForAndSendSomething(ctx, "register", rawAuthor=ctx.author, reply=lambda a: ctx.respond(a, ephemeral=True))
    

@bot.command(description="Checkout someone's current number of chips!")
@discord.option("user", discord.User, description = "The player who you want to check out! (default is you)", required = False, default = None)
async def userinfo(ctx: discord.ApplicationContext, user: discord.User):
    await parseCommandForAndSendSomething(ctx, f"userinfo {user.id if user else ''}", rawAuthor=ctx.author, reply=lambda a: ctx.respond(a, ephemeral=True))
    

@bot.command(description="Give someone chips so they can keep messing around!")
@discord.option("user", discord.User, description = "The player who you want to check out! (default is you)", required = True)
@discord.option("amount", int, description = "How many chips to give.", required = True)
async def add_chips(ctx: discord.ApplicationContext, user: discord.User, amount: int):
    await parseCommandForAndSendSomething(ctx, f"addchips {user.id} {amount}", rawAuthor=ctx.author, reply=lambda a: ctx.respond(a, ephemeral=True))

@bot.command(description="List the top 10 players")
async def leaderboards(ctx: discord.ApplicationContext):
    await parseCommandForAndSendSomething(ctx, f"leaderboards", rawAuthor=ctx.author, reply=lambda a: ctx.channel.send(a))

@bot.command(description="Checkout how to use this bot!")
async def help(ctx: discord.ApplicationContext):
    await parseCommandForAndSendSomething(ctx, "help", rawAuthor=ctx.author, reply=lambda a: ctx.respond(a, ephemeral=True))
    
@bot.command(description="Checkout game's details!")
@discord.option("gameid", int, description = "Id of the game you're interested in.", required = True)
async def gameinfo(ctx: discord.ApplicationContext, gameid: int):
    await parseCommandForAndSendSomething(ctx, f"gameinfo {gameid}", rawAuthor=ctx.author, reply=lambda a: ctx.channel.send(a))

@bot.command(description="List all games")
@discord.option("open", bool)
@discord.option("in_progress", bool)
@discord.option("finished", bool)
@discord.option("aborted", bool)
@discord.option("with_player", discord.User, default = None, required = False)
async def list_games(ctx: discord.ApplicationContext, open: bool, in_progress: bool, finished: bool, aborted: bool, with_player: discord.User):
    await parseCommandForAndSendSomething(ctx, f"list {'open ' if open else ''}{'done ' if finished else ''}{'playing ' if in_progress else ''}{f'with {with_player}' if with_player else ''}", rawAuthor=ctx.author, reply=lambda a: ctx.channel.send(a))



@bot.command()
async def shutdown(ctx: discord.ApplicationContext):
    if await bot.is_owner(ctx.user):
        await ctx.respond("Exiting")
        sys.exit()
    await ctx.respond("No Permissions")

bot.run(TOKEN)