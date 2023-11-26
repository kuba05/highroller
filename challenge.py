from __future__ import annotations
from typing import Optional, cast, Type, Self
import time
import datetime

from constants import ChallengeState
from db import Database

import player as playerModule


class Challenge:
    """
    Object to represent a challenge created by players.

    Should be constructed using following factory methods:
    - precreate
    - getById
    - getByMessageId
    - getAllChallengesByState
    - getNewTimeouts
    """
    db: Optional[Database] = None

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


    """
    TO STR
    """

    async def toTextForMessages(self) -> str:
        """
        Creates a formated message explaining what this challenge is about
        """
        stateMessage = ""
        if self.state == ChallengeState.ABORTED:
            stateMessage = " (aborted)"
        if self.winner != None:
            stateMessage = f" (winner: {await cast(playerModule.Player, playerModule.Player.getById(self.winner)).getName()})"
        return f"Challenge {self.id} {await cast(playerModule.Player, playerModule.Player.getById(self.authorId)).getName()} vs {await cast(playerModule.Player, playerModule.Player.getById(self.acceptedBy)).getName() if self.acceptedBy else 'TBD'}" + stateMessage
        
    def __str__(self):
        return f"Challenge {self.id} by {self.authorId}. State {self.state}. Bet {self.bet}. Timeout: {datetime.datetime.fromtimestamp(self.timeout)} Notes:\"{self.notes}\""
    

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
    FACTORY METHODS
    """

    @classmethod
    def precreate(cls: Type[Self], bet: int, authorId: int, map:str, tribe: str, lastsForMinutes: int, notes: str = "") -> Self:
        """
        Creates a challenge object with no connection to database.

        To connect it to DB, call finishCreating method

        Returns:
            The object created

        Raises:
            ValueError - if author isn't registered or doesn't have enough chips
        """
        author = playerModule.Player.getById(authorId)
        if author == None:
            raise ValueError("You are not registered!")
        
        author = cast(playerModule.Player, author)
        if author.currentChips < bet:
            raise ValueError("You don't have enough chips")

        # let's use a proxy value of -1 for id
        challenge = cls(id = cls.getDb().getNewIdForChallenge(), messageId=None, bet=bet, authorId=authorId, acceptedBy=None, state=ChallengeState.PRECREATED, timeout=int(time.time() + lastsForMinutes*60), map=map, tribe=tribe, notes=notes, gameName=None, winner=None)
        return challenge

    @classmethod
    def getById(cls: Type[Self], id: int) -> Optional[Self]:
        """
        Returns challenge with given id from db, or None if there is no match.

        Returns:
            The object found or None if nothing was found

        Raises:
            Nothing
        """
        challengeData = cls.getDb().getChallengeById(id)
        if challengeData == None:
            return None
        else:
            return cls(*challengeData)

    @classmethod
    def getByMessageId(cls: Type[Self], messageId: int) -> Optional[Self]:
        """
        Returns challenge with given messageId from db, or None if there is no match.

        Returns:
            The object found or None if nothing was found

        Raises:
            Nothing
        """
        challengeData = cls.getDb().getChallengeByMessageId(messageId)
        if challengeData == None:
            return None
        else:
            return cls(*challengeData)

    @classmethod
    def getAllChallengesByState(cls: Type[Self], state: ChallengeState) -> list[Self]:
        """
        Returns a list of all challenges with matching state


        Returns:
            List of all objects found

        Raises:
            Nothing
        """
        return [cls(*challenge) for challenge in cls.getDb().getChallengesByState(state)]

    @classmethod
    def getNewTimeouts(cls: Type[Self]) -> list[Self]:
        """
        Returns a list of all challenges which should timeout
        """
        return [cls(*challenge) for challenge in cls.getDb().getTimeoutedChallengesByStateAndTimeoutTime(ChallengeState.CREATED, int(time.time()))]


    """
    STORY METHODS
    """

    def finishCreating(self, messageId: int | None) -> None:
        """
        Finishes createing the Challenge, setting messageId, writing the challenge into db and charging the author chips.

        Can be used only when challenge is PRECREATED

        Returns:
            Nothing

        Raises:
            ValueError - if Challenge's state isn't correct
        """
        if self.state != ChallengeState.PRECREATED:
            raise ValueError("can't create a challange that's already created!")
        self.messageId = messageId
        self.state = ChallengeState.CREATED
        self.getDb().adjustPlayerChips(self.authorId, -self.bet)
        self.getDb().createChallenge(challangeId=self.id, messageId=self.messageId, bet=self.bet, authorId=self.authorId, acceptedBy=self.acceptedBy, state=self.state, timeout=self.timeout, map=self.map, tribe=self.tribe, notes=self.notes, gameName=self.gameName, winner=self.winner)
        
    def accept(self, playerId: int) -> None:
        """
        Make given player accept this challange

        Returns:
            Nothing

        Raises:
            ValueError - if Challenge's state isn't correct, the player isn't registered or the player doesn't have enough chips
        """
        if self.state != ChallengeState.CREATED:
            raise ValueError("Challenge has already been accepted!")
        
        # TODO: disabled for testing
        #if self.authorId == playerId:
        #    raise ValueError("You can't accept your own challenge!")
        
        player = playerModule.Player.getById(playerId)
        if player == None:
            raise ValueError("You are not registered!")
        player = cast(playerModule.Player, player)
        if player.currentChips < self.bet:
            raise ValueError("You don't have enough chips")
        
        self.getDb().setChallengeState(self.id, ChallengeState.ACCEPTED)
        self.state = ChallengeState.ACCEPTED

        self.getDb().setChallengeAcceptedBy(self.id, playerId)
        self.acceptedBy = playerId

        self.getDb().adjustPlayerChips(playerId, - self.bet)

    def start(self, playerId: int, gameName: str) -> None:
        """
        Make given player start this challange with given name

        Returns:
            Nothing

        Raises:
            ValueError - if Challenge's state isn't correct or the player isn't the author
        """
        if playerId != self.authorId:
            raise ValueError("You can't start a game you're not hosting!")
        
        if self.state != ChallengeState.ACCEPTED:
            raise ValueError("The game can't be started!")
        
        self.getDb().setChallengeName(self.id, gameName)
        self.gameName = gameName

        self.getDb().setChallengeState(self.id, ChallengeState.STARTED)
        self.state = ChallengeState.STARTED

    def claimVictory(self, winnerId: int, force: bool) -> None:
        """
        Make given player claim the victory of this challange

        Force can turn off checking the state.

        Returns:
            Nothing

        Raises:
            ValueError - if Challenge's state isn't correct or winner isn't part of the game
        """
        if winnerId not in [self.authorId, self.acceptedBy]:
            raise ValueError("You can't finish a game you're not part of!")
        
        if force or self.state != ChallengeState.STARTED:
            raise ValueError("The game can't be finished!")
        
        self.getDb().setChallengeState(self.id, ChallengeState.FINISHED)
        self.state = ChallengeState.FINISHED

        self.getDb().setChallengeWinner(self.id, winnerId)
        self.winner = winnerId

        self.getDb().adjustPlayerChips(winnerId, self.bet*2)

    def abort(self, byPlayer: int, force: bool) -> None:
        """
        Make given player abort this challange.

        if byPlayer is None, the system is assumed to have aborted the challange

        Force can turn off checking the state and byPlayer

        Returns:
            Nothing

        Raises:
            ValueError - if Challenge's state isn't correct or byPlayer isn't part of the game
        """
        if force or byPlayer not in [self.authorId, self.acceptedBy, None]:
            raise ValueError("You can't abort a game you're not part of!")
        
        if force or self.state not in [ChallengeState.CREATED, ChallengeState.ACCEPTED]:
            raise ValueError("Can't abort game that has already been started!")
        
        self.getDb().setChallengeState(self.id, ChallengeState.ABORTED)
        self.getDb().adjustPlayerChips(self.authorId, self.bet)

        if self.acceptedBy != None:
            self.getDb().adjustPlayerChips(cast(int, self.acceptedBy), self.bet)
            self.getDb().increasePlayerAbortedCounter(byPlayer)

    def unwin(self) -> None:
        """
        Revokes the victory of the winner.

        Returns:
            Nothing

        Raises:
            ValueError - if winner doesn't have the chips anymore
        """
        if not self.winner:
            # if no winner, there's nothing to do
            return
        
        cast(playerModule.Player, playerModule.Player.getById(self.winner)).adjustChips(-2*self.bet)

        self.getDb().setChallengeState(self.id, ChallengeState.STARTED)
        self.state = ChallengeState.STARTED
