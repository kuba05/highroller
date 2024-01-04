from __future__ import annotations
from typing import Optional, cast, Type, Self

import discord

from constants import ChallengeState, STARTING_CHIPS, TEAM_ROLES
from db import Database
import myTypes

class Player:
    """
    Object to represent any player (discord user registered to this game).

    Should be created using following factory methods:
    - create
    - getById
    - getTopPlayersThisSeason
    - getTopPlayersAllTime
    """

    bot: Optional[myTypes.botWithGuild] = None
    db: Optional[Database] = None

    def __init__(self, playerId: int, currentChips: int, totalChips: int, abortedGames: int):
        self.id = playerId
        self.currentChips = currentChips
        self.totalChips = totalChips
        self.abortedGames = abortedGames
        self.dmChannel = None



    """
    DATABASE
    """

    @classmethod
    def setDb(cls: Type[Self], db: Database) -> None:
        """
        set database for all Challenges to use
        """
        cls.db = db

    @classmethod
    def getDb(cls: Type[Self]) -> Database:
        """
        return the database all Challenges are using
        """
        if cls.db != None:
            return cast(Database, cls.db)
        raise EnvironmentError(f"Database of {cls} not set!")



    """
    BOT
    """

    @classmethod
    def setBot(cls: Type[Self], bot: myTypes.botWithGuild) -> None:
        """
        set database for all Challenges to use
        """
        cls.bot = bot

    @classmethod
    def getBot(cls: Type[Self]) -> myTypes.botWithGuild:
        """
        return the database all Challenges are using
        """
        if cls.bot != None:
            return cast(myTypes.botWithGuild, cls.bot)
        raise EnvironmentError(f"Bot of {cls} not set!")


    @classmethod
    def giveAllPlayersChips(cls: Type[Self], amount: int) -> None:
        cls.getDb().giveAllPlayersChips(amount)

    @classmethod
    def resetAllPlayersCurrentChips(cls: Type[Self]) -> None:
        cls.getDb().setAllCurrentChips(STARTING_CHIPS)
        
    """
    FACTORY METHODS
    """

    @classmethod
    def create(cls: Type[Self], playerId: int) -> Self:
        """
        Register a new player to the game. If player with same id already exists, ValueError is raised.

        Returns:
            object created

        Raises:
            ValueError - if player is already registered
        """
        if cls.getById(playerId) != None:
            raise ValueError("You are already registered!")

        player = cls(playerId, STARTING_CHIPS, STARTING_CHIPS, 0)
        cls.getDb().createPlayer(player.id, player.currentChips, player.totalChips, player.abortedGames)
        return player

    @classmethod
    def getById(cls: Type[Self], id: Optional[int]) -> Optional[Self]:
        """
        Returns player with given id from db, or None if there is no match.

        Returns:
            object found or None if nothing's found

        Raises:
            Nothing
        """
        playerData = cls.getDb().getPlayer(id)
        if playerData == None:
            return None
        else:
            return cls(*playerData)
    
    @classmethod
    def getAll(cls: Type[Self]) -> list[Self]:
        """
        Returns a list of all players ever registered.

        Raises:
            Nothing
        """
        return [cls(*playerData) for playerData in cls.getDb().getAllPlayers()]

    @classmethod
    def getTopPlayersThisSeason(cls: Type[Self], count: int) -> list[Self]:
        """
        Returns a list of players with the most chips in this season in descending order. The list has length [count].

        Returns:
            list of the top [count] players

        Raises:
            Nothing
        """
        return [cls(*playerData) for playerData in cls.getDb().getTopPlayersThisEpoch(count)]
    
    @classmethod
    def getTopPlayersAllTime(cls: Type[Self], count: int) -> list[Self]:
        """
        Returns a list of players with the most chips in all seasons combined in descending order. The list has length [count].

        Returns:
            list of the top [count] players

        Raises:
            Nothing
        """
        return [cls(*playerData) for playerData in cls.getDb().getTopPlayersTotal(count)]
    


    """
    STORY METHODS
    """

    async def DM(self, message: str) -> bool:
        """
        Send DM to the user. Returns if sending the message was successful.

        Returns:
            If DM was delivered

        Raises:
            Nothing
        """
        member = await self.getBot().fetch_user(self.id)
        try:
            await member.send(message)
        except discord.errors.Forbidden:
            return False
        return True
    
    async def getName(self) -> str:
        member = await self.getBot().get_or_fetch_user(self.id)
        return member.name
        
    async def getTeam(self) -> int:
        """
        return number coresponding to the index of team who's role this user has, returns -1 if not in a team
        """
        member = await self.getBot().get_or_fetch_user(self.id)
        for i, role in TEAM_ROLES:
            if role in [role.id for role in member.roles]:
                return i
        return -1

    def adjustChips(self, number: int) -> None:
        """
        Gives the player [number] of chips.

        Returns:
            Nothing

        Raises:
            ValueError - if final amount of chips would be negative
        """
        if self.currentChips + number < 0:
            raise ValueError("You can't have negative chips!")
        self.getDb().adjustPlayerChips(self.id, number)
        self.currentChips += number
        self.totalChips += number
        
    def getGameScore(self) -> list[int]:
        wr = self.getDb().getPlayersWinrate(self.id)
        return [wr[0], wr[1]]

