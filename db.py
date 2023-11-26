from enum import Enum
import sqlite3
import sys
import time
import os

from typing import Optional, Any, cast

import logging

class Database:
    def __init__(self, name):
        self.con = sqlite3.connect(name)
        self.con.execute("PRAGMA foreign_keys = 1")

        self.con.executescript("""
        BEGIN;
        CREATE TABLE IF NOT EXISTS "challenges"
        (
            [id] INTEGER PRIMARY KEY NOT NULL,
            [messageId] INTEGER UNIQUE,
            [bet] INTEGER CHECK (bet > 0),
            [authorId] INTEGER NOT NULL,
            [acceptedBy] INTEGER,
            [state] INTEGER,
            [timeout] INTEGER,
            [map] TEXT,
            [tribe] TEXT,
            [notes] TEXT,
            [gameName] TEXT,
            [winner] INTEGER,
            FOREIGN KEY(authorId) REFERENCES players(playerId),
            FOREIGN KEY(acceptedBy) REFERENCES players(playerId),
            FOREIGN KEY(winner) REFERENCES players(playerId)
        );
        CREATE INDEX IF NOT EXISTS [challengesByAuthorsIndex] ON "challenges" ([authorId]);

        CREATE TABLE IF NOT EXISTS "players"
        (
            [playerId] INTEGER PRIMARY KEY NOT NULL,
            [currentChips] INTEGER check (currentChips >= 0),
            [totalChips] INTEGER check (totalChips >= 0),
            [abortedGamesTotal] INTEGER
        );
        COMMIT;
        """)

    def createChallenge(self, challangeId: int, messageId: Optional[int], bet: int, authorId: int, acceptedBy: Optional[int], state: Enum, timeout: Optional[int], map: str, tribe: str, notes: str, gameName: Optional[str], winner: Optional[int]) -> None:
        logging.info(f"creating challenge with params: {challangeId}, {messageId}, {bet}, {authorId}, {acceptedBy}, {state}, {timeout}, {notes}, {gameName}, {winner}")
        try:
            self.con.execute('INSERT INTO challenges VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);', (challangeId, messageId, bet, authorId, acceptedBy, state.value, timeout, map, tribe, notes, gameName, winner))
            self.con.commit()

        except Exception as e:
            logging.error(f"Error creating challange {challangeId}")
            logging.error(str(e))
            self.con.rollback()

    def getChallengeById(self, challengeId) -> list[Any]:
        return self.con.execute('SELECT * FROM challenges WHERE id = ?;', (challengeId,)).fetchone()
    
    def getChallengeByMessageId(self, messageId) -> list[Any]:
        return self.con.execute('SELECT * FROM challenges WHERE messageId = ?;', (messageId,)).fetchone()
    
    def setChallengeState(self, challengeId: int, challengeState: Enum) -> None:
        try:
            self.con.execute('UPDATE challenges SET state = ? WHERE id = ?', (challengeState.value, challengeId))
            self.con.commit()

        except Exception as e:
            logging.error(f"Error setting state of a challange {challengeId}")
            logging.error(str(e))
            self.con.rollback()

    def setChallengeAcceptedBy(self, challengeId: int, acceptedBy: int) -> None:
        try:
            self.con.execute('UPDATE challenges SET acceptedBy = ? WHERE id = ?', (acceptedBy, challengeId))
            self.con.commit()
        except Exception as e:
            logging.error(f"Error accepting a challange {challengeId}")
            logging.error(str(e))
            self.con.rollback()

    def setChallengeName(self, challengeId: int, name: str) -> None:
        try:
            self.con.execute('UPDATE challenges SET gameName = ? WHERE id = ?', (name, challengeId))
            self.con.commit()
        except Exception as e:
            logging.error(f"Error setting name of a challange {challengeId}")
            logging.error(str(e))
            self.con.rollback()
    
    def setChallengeWinner(self, challengeId: int, winnerId: int) -> None:
        try:
            self.con.execute('UPDATE challenges SET winner = ? WHERE id = ?', (winnerId, challengeId))
            self.con.commit()
        except Exception as e:
            logging.error(f"Error setting winner of a challange {challengeId}")
            logging.error(str(e))
            self.con.rollback()

    def getNewIdForChallenge(self) -> int:
        while True:
            newId = int.from_bytes(os.urandom(7))

            # id is not yet used
            if self.getChallengeById(newId) == None:
                return newId

    def getChallengesByState(self, state: Enum) -> list[list[Any]]:
        return self.con.execute('SELECT * FROM challenges WHERE state = ?', (state.value, )).fetchall()

    def getTimeoutedChallengesByStateAndTimeoutTime(self, state: Enum, timeoutTime: int) -> list[list[Any]]:
        return self.con.execute('SELECT * FROM challenges WHERE state = ? AND timeout <= ?', (state.value, timeoutTime)).fetchall()






    def createPlayer(self, playerId, currentChips, totalChips, abortedGames) -> None:
        try:
            self.con.execute('INSERT INTO players VALUES (?, ?, ?, ?);', (playerId, currentChips, totalChips, abortedGames))
            self.con.commit()

        except Exception as e:
            logging.error(f"Error creating player {playerId}")
            logging.error(str(e))
            self.con.rollback()

    def getPlayer(self, playerId):
        return self.con.execute('SELECT * FROM players WHERE playerId = ?', (playerId,)).fetchone()
    
    def increasePlayerAbortedCounter(self, playerId: int) -> None:
        try:
            self.con.execute('UPDATE players SET abortedGamesTotal = abortedGamesTotal + 1 WHERE playerId = ?', (playerId,))
            self.con.commit()
        except Exception as e:
            logging.error(f"Error increasing player abort counter {playerId}")
            logging.error(str(e))
            self.con.rollback()

    def adjustPlayerChips(self, playerId: int, changeOfChips: int) -> None:
        try:
            self.con.execute('UPDATE players SET currentChips = currentChips + ?, totalChips = totalChips + ? WHERE playerId = ?', (changeOfChips, changeOfChips, playerId,))
            self.con.commit()
        except Exception as e:
            logging.error(f"Error adjusting player chips counter {playerId}")
            logging.error(str(e))
            self.con.rollback()

    def getPlayersWinrate(self, playerId: int) -> list[int]:
        return [
            cast(int, self.con.execute('SELECT COUNT(messageId) FROM challenges WHERE winner = ? AND NOT (state = 7 OR state = 1)', (playerId,)).fetchone()[0]),
            cast(int,self.con.execute('SELECT COUNT(messageId) FROM challenges WHERE (authorId = ? OR acceptedBy = ?) AND NOT (state = 7 OR state = 1)', (playerId, playerId)).fetchone()[0])
        ]

    def getTopPlayersThisEpoch(self, limit=10) -> list[list[Any]]:
        return self.con.execute('SELECT * FROM players ORDER BY currentChips DESC LIMIT ?', (limit, )).fetchall()

    def getTopPlayersTotal(self, limit=10) -> list[list[Any]]:
        return self.con.execute('SELECT * FROM players ORDER BY totalChips DESC LIMIT ?', (limit, )).fetchall()




            

if __name__ == "__main__":
    pass