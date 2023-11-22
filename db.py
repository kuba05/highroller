from enum import Enum
import sqlite3
import sys
import time
import os

from typing import Optional, Any, cast

class Database:
    def __init__(self, name):
        self.con = sqlite3.connect(name)
        self.con.execute("PRAGMA foreign_keys = 1")

        self.con.executescript("""
        BEGIN;
        CREATE TABLE IF NOT EXISTS "challenges"
        (
            [messageId] INTEGER PRIMARY KEY NOT NULL,
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

    def createChallenge(self, messageId: int, bet: int, authorId: int, acceptedBy: Optional[int], state: Enum, timeout: Optional[int], map: str, tribe: str, notes: str, gameName: Optional[str], winner: Optional[int]) -> None:
        print(f"creating challenge with params: {messageId}, {bet}, {authorId}, {acceptedBy}, {state}, {timeout}, {notes}, {gameName}, {winner}", file=sys.stderr, flush=True)
        try:
            self.con.execute('INSERT INTO challenges VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);', (messageId, bet, authorId, acceptedBy, state.value, timeout, map, tribe, notes, gameName, winner))
            self.con.commit()

        except Exception as e:
            print(e, file=sys.stderr)
            self.con.rollback()

    def getChallenge(self, challengeId) -> list[Any]:
        return self.con.execute('SELECT * FROM challenges WHERE messageId = ?;', (challengeId,)).fetchone()
    
    def setChallengeState(self, challengeId: int, challengeState: Enum) -> None:
        try:
            self.con.execute('UPDATE challenges SET state = ? WHERE messageId = ?', (challengeState.value, challengeId))
            self.con.commit()

        except Exception as e:
            print(e, file=sys.stderr)
            self.con.rollback()

    def setChallengeAcceptedBy(self, challengeId: int, acceptedBy: int) -> None:
        try:
            self.con.execute('UPDATE challenges SET acceptedBy = ? WHERE messageId = ?', (acceptedBy, challengeId))
            self.con.commit()
        except Exception as e:
            print(e, file=sys.stderr)
            self.con.rollback()

    def setChallengeName(self, challengeId: int, name: str) -> None:
        try:
            self.con.execute('UPDATE challenges SET gameName = ? WHERE messageId = ?', (name, challengeId))
            self.con.commit()
        except Exception as e:
            print(e, file=sys.stderr)
            self.con.rollback()
    
    def setChallengeWinner(self, challengeId: int, winnerId: int) -> None:
        try:
            self.con.execute('UPDATE challenges SET winner = ? WHERE messageId = ?', (winnerId, challengeId))
            self.con.commit()
        except Exception as e:
            print(e, file=sys.stderr)
            self.con.rollback()


    def createPlayer(self, playerId, currentChips, totalChips, abortedGames) -> None:
        try:
            self.con.execute('INSERT INTO players VALUES (?, ?, ?, ?);', (playerId, currentChips, totalChips, abortedGames))
            self.con.commit()

        except Exception as e:
            print(e, file=sys.stderr)
            self.con.rollback()

    def getPlayer(self, playerId):
        return self.con.execute('SELECT * FROM players WHERE playerId = ?', (playerId,)).fetchone()
    
    def increasePlayerAbortedCounter(self, playerId: int) -> None:
        try:
            self.con.execute('UPDATE players SET abortedGamesTotal = abortedGamesTotal + 1 WHERE playerId = ?', (playerId,))
            self.con.commit()
        except Exception as e:
            print(e, file=sys.stderr)
            self.con.rollback()

    def adjustPlayerChips(self, playerId: int, changeOfChips: int) -> None:
        try:
            self.con.execute('UPDATE players SET currentChips = currentChips + ?, totalChips = totalChips + ? WHERE playerId = ?', (changeOfChips, changeOfChips, playerId,))
            self.con.commit()
        except Exception as e:
            print(e, file=sys.stderr)
            self.con.rollback()

    def getPlayersWinrate(self, playerId: int) -> list[int]:
        return [
            cast(int, self.con.execute('SELECT COUNT(messageId) FROM challenges WHERE winner = ? AND NOT (state = 7 OR state = 1)', (playerId,)).fetchone()[0]),
            cast(int,self.con.execute('SELECT COUNT(messageId) FROM challenges WHERE (authorId = ? OR acceptedBy = ?) AND NOT (state = 7 OR state = 1)', (playerId, playerId)).fetchone()[0])
        ]

    def getTopPlayersThisEpoch(self, limit=10) -> list[list[Any]]:
        return self.con.execute('SELECT * FROM players ORDER BY currentChips LIMIT ?', (limit, )).fetchall()

    def getTopPlayersTotal(self, limit=10) -> list[list[Any]]:
        return self.con.execute('SELECT * FROM players ORDER BY totalChips LIMIT ?', (limit, )).fetchall()






    def getChallengesByState(self, state: Enum) -> list[list[Any]]:
        return self.con.execute('SELECT * FROM challenges WHERE state = ?', (state.value, )).fetchall()

    def getTimeoutedChallengesByStateAndTimeoutTime(self, state: Enum, timeoutTime: int) -> list[list[Any]]:
        return self.con.execute('SELECT * FROM challenges WHERE state = ? AND timeout <= ?', (state.value, timeoutTime)).fetchall()

            

if __name__ == "__main__":
    pass