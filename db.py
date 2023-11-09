from enum import Enum
import sqlite3
import sys
import time
import os

from typing import Optional

#status:
#0 not accepted
#1 accepted
#2 started
#3 won by host
#4 won by away
#5 aborted manually
#6 aborted because time ran out
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
            [status] INTEGER,
            [timeout] INTEGER,
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

    def createChallenge(self, messageId: int, bet: int, authorId: int, acceptedBy: Optional[int], status: int, timeout: Optional[int], notes: str, gameName: Optional[str], winner: Optional[int]) -> None:
        print(f"creating challenge with params: {messageId}, {bet}, {authorId}, {acceptedBy}, {status}, {timeout}, {notes}, {gameName}, {winner}", file=sys.stderr, flush=True)
        try:
            self.con.execute('INSERT INTO challenges VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);', (messageId, bet, authorId, acceptedBy, status, timeout, notes, gameName, winner))
            self.con.commit()

        except Exception as e:
            print(e, file=sys.stderr)
            self.con.rollback()

    def getChallenge(self, challengeId):
        return self.con.execute('SELECT * FROM challenges WHERE messageId = ?;', (challengeId,)).fetchone()
    
    def setChallengeState(self, challengeId: int, challengeState: Enum) -> None:
        try:
            self.con.execute('UPDATE challenges SET status = ? WHERE messageId = ?', (challengeState.value, challengeId,))
            self.con.commit()

        except Exception as e:
            print(e, file=sys.stderr)
            self.con.rollback()

    def setChallengeAcceptedBy(self, challengeId: int, acceptedBy: int) -> None:
        try:
            self.con.execute('UPDATE challenges SET acceptedBy = ? WHERE messageId = ?', (acceptedBy, challengeId,))
            self.con.commit()
        except Exception as e:
            print(e, file=sys.stderr)
            self.con.rollback()

    def setChallengeName(self, challengeId: int, name: str) -> None:
        pass
    
    def setChallengeWinner(self, challengeId: int, playerId: int) -> None:
        pass


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
        return (self.con.execute('SELECT COUNT(messageId) FROM challenges WHERE winner = ?', (playerId,)).fetchone()[0], self.con.execute('SELECT COUNT(messageId) FROM challenges WHERE authorId = ? OR acceptedBy = ?', (playerId, playerId)).fetchone()[0])

    def getTopPlayersThisEpoch(self, limit=10):
        return self.con.execute('SELECT * FROM players ORDER BY currentChips LIMIT ?', (limit, )).fetchall()

    def getTopPlayersTotal(self, limit=10):
        return self.con.execute('SELECT * FROM players ORDER BY totalChips LIMIT ?', (limit, )).fetchall()






    def getChallenges(self, status=None):
        try:
            if status == None:
                return self.con.execute('SELECT * FROM challenges;').fetchall()
            return self.con.execute('SELECT * FROM challenges WHERE status = ?;', (status,)).fetchall()

        except Exception as e:
            print(e, file=sys.stderr, flush=True)
            self.con.rollback()
            if type(e) == ValueError:
                raise e
            else:
                raise ValueError("Something went wrong!")
            

if __name__ == "__main__":
    os.remove("test1.db") 
    db = Database("test1.db")
    db.createPlayer(1)
    db.createPlayer(2)

    db.createChallenge(10, 1, 1, 60, "ahoj")
    db.abortChallenge(10, 1)
    input("x")

    db.createChallenge(11, 1, 1, 60, "ahoj")
    db.acceptChallenge(11,2)
    db.abortChallenge(11, 1)
    input("x")


    db.createChallenge(12, 1, 1, 60, "ahoj")
    db.acceptChallenge(12,2)
    db.startChallenge(12, "ass")
    input("x")

    db.winChallenge(12,True)
    print(db.getChallenge(20))