from __future__ import annotations
from typing import Optional, cast
import logging

import discord

from constants import ChallengeState, ABORT_EMOJI, ACCEPT_EMOJI

import challenge as challengeModule
#import Challenge
import player as playerModule
#import Player


class Messenger:
    """
    Object to make sending messages easier.

    Should be created with create factory method.
    """
    messageChannel: discord.TextChannel
    spamChannel: discord.TextChannel
    messages: set[int]

    @staticmethod
    async def create(messageChannelId: int, spamChannelId: int, bot: discord.Bot) -> Messenger:
        """
        Creates Messenger object and links messageChannel to it.
        """
        messenger = Messenger()

        messenger.spamChannel: discord.TextChannel = await bot.fetch_channel(spamChannelId) # type: ignore
        messenger.messageChannel: discord.TextChannel = await bot.fetch_channel(messageChannelId) # type: ignore

        messenger.messages =  set()
        logging.debug(f"message channel: {messenger.messageChannel} (server: {messenger.messageChannel.guild})")
        return messenger

    async def _DM (self, player: playerModule.Player|None, message: str):
        if player != None:
            await cast(playerModule.Player, player).DM(message=message)


    async def _sendAll(self, challenge: challengeModule.Challenge, message: str) -> None:
        """
        Send all players associated with given challange DMs with given message.
        """
        await self._sendHost(challenge=challenge, message=message)
        await self._sendAway(challenge=challenge, message=message)

    async def _sendHost(self, challenge: challengeModule.Challenge, message: str) -> None:
        """
        Send the host of a given challange (if exists) a DM with given message.
        """
        await self._DM(player=playerModule.Player.getById(challenge.authorId), message=message)

    async def _sendAway(self, challenge: challengeModule.Challenge, message: str) -> None:
        """
        Send the away player of a given challange (if exists) a DM with given message.
        """
        await self._DM(player=playerModule.Player.getById(challenge.acceptedBy), message=message)

    async def _deleteChallengeMessage(self, challenge: challengeModule.Challenge) -> None:
        if challenge.messageId:
            message = await self.messageChannel.fetch_message(cast(int, challenge.messageId))
            self.messages.discard(challenge.messageId)
            await message.delete()

    async def loadAllChallengesAfterRestart(self) -> None:
        for challange in challengeModule.Challenge.getAllChallengesByState(state=ChallengeState.CREATED):
            if challange.messageId != None:
                self.messages.add(cast(int,challange.messageId))
            logging.info("Loaded a challenge after restart!")


    """
    STORY METHODS
    """

    async def createChallengeEntry(self, challenge: challengeModule.Challenge, private: bool) -> None:
        """
        Creates the message entry for given challange. Then finishes creating the challange.

        if private is true, no message will be generated.
        """
        logging.info(f"Created challenge: {str(challenge)} (private: {private})")
        if not private:
            name = cast(playerModule.Player, playerModule.Player.getById(challenge.authorId)).getName()
            message = await self.messageChannel.send(
f"""
## ⚔️ {name} challanges you! ⚔️
bet: {challenge.bet}
map: {challenge.map}
tribe: {challenge.tribe}
timelimit: 24 hours

challange timeouts in <t:{challenge.timeout}:t>
"""
            )
            await self._sendHost(challenge, f"{await challenge.toTextForMessages()} has been created")
            self.messages.add(cast(int, message.id))
            await message.add_reaction(ABORT_EMOJI)
            await message.add_reaction(ACCEPT_EMOJI)
            challenge.finishCreating(message.id)
        else:
            await self._sendHost(challenge, f"{await challenge.toTextForMessages()} has been created.\n"\
                "The challange is private, so it won't show up in listings."\
                "If you want someone to connect, they have to DM me the following command:\n"\
                f"accept {challenge.id}")
            challenge.finishCreating(None)
    
    async def abortChallenge(self, challenge: challengeModule.Challenge) -> None:
        await self._sendAll(challenge, f"{await challenge.toTextForMessages()} has been aborted.\n"\
            "If you wish to create another one, use the /create_challenge command!")

        await self._deleteChallengeMessage(challenge)

        logging.info(f"challenge aborted {challenge.id}")

    async def abortChallengeDueTimeout(self, challenge: challengeModule.Challenge) -> None:
        await self._sendAll(challenge, f"{await challenge.toTextForMessages()} has been aborted due timeout.\n"\
            "If you wish to create another one, use the /create_challenge command!")

        await self._deleteChallengeMessage(challenge)

        logging.info(f"challenge aborted due timeout {challenge.id}")

    async def acceptChallenge(self, challenge: challengeModule.Challenge) -> None:
        await self._deleteChallengeMessage(challenge)
        await self._sendAway(challenge, f"{await challenge.toTextForMessages()} has been accepted.\n"\
            "Waiting for host to start the game")
        await self._sendHost(challenge, f"{await challenge.toTextForMessages()} has been accepted.\n"\
            f"Please start the game by sending me the following command:\nstart {challenge.id} [gamename]")

        logging.info(f"challenge accepted {challenge.id}")

    async def startChallenge(self, challenge: challengeModule.Challenge) -> None:
        await self._sendAll(challenge, f"{await challenge.toTextForMessages()} has been started! \nThe game name is {challenge.gameName}\n\nGLHF!"\
            f"Once the game is over, the winner should send me the following command:\nwin {challenge.id} ")
        logging.info(f"started {challenge.id}")

    async def claimChallenge(self, challenge: challengeModule.Challenge) -> None:
        await self._sendAll(challenge, f"{await challenge.toTextForMessages()} has been claimed by {cast(playerModule.Player, playerModule.Player.getById(challenge.winner)).getName()}! \nIf you want to dispute the claim, contact the mods!")
        logging.info(f"claimed {challenge.id}")


    async def playerRegistered(self, playerId: int) -> None:
        await self._DM(playerModule.Player.getById(playerId), "You have registered to Highroller tournament! Good luck have fun :D")
        await self.spamChannel.send(f"<@{playerId}> you have registered! Please check your DMs, you should have one from me :D")
