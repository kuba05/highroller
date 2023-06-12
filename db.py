import sqlite3
import sys
import time
import os

#status:
#0 not accepted
#1 accepted
#2 started
#3 won by host
#4 won by away
#5 aborted manually
#6 aborted because time ran out

class Database:
    def __init__(self, name, MOCK):
        self.con = sqlite3.connect(name)
        self.con.execute("PRAGMA foreign_keys = 1")

        self.MOCK = MOCK

        self.con.executescript("""
        BEGIN;
        CREATE TABLE IF NOT EXISTS "challenges"
        (
            [messageId] INTEGER PRIMARY KEY NOT NULL,
            [bet] INTEGER CHECK (bet > 0),
            [authorId] INTEGER  NOT NULL,
            [acceptedBy] INTEGER,
            [status] INTEGER default 0,
            [timeout] INTEGER,
            [notes] TEXT,
            [gameName] TEXT default NULL,
            FOREIGN KEY(authorId) REFERENCES players(playerId),
            FOREIGN KEY(acceptedBy) REFERENCES players(playerId)
        );
        CREATE INDEX IF NOT EXISTS [challengesByAuthorsIndex] ON "challenges" ([authorId]);

        CREATE TABLE IF NOT EXISTS "players"
        (
            [playerId] INTEGER PRIMARY KEY NOT NULL,
            [currentChips] INTEGER default 0 check (currentChips >= 0),
            [totalChips] INTEGER default 0 check (totalChips >= 0),
            [abortedGamesTotal] INTEGER default 0
        );
        COMMIT;
        """)

    def createChallenge(self, messageId, bet, authorId, lastForMinutes, notes):

        print(f"creating challenge with params: {messageId}, {bet}, {authorId}, {lastForMinutes}, {notes}", file=sys.stderr, flush=True)

        timeout = int(time.time() + lastForMinutes*60)

        errorMessage = "Something went wrong!"

        try:
            errorMessage = "Player doesn't exist! Please register with /register command"
            self.con.execute('INSERT INTO challenges VALUES (?, ?, ?, NULL, 0, ?, ?, NULL);', (messageId, bet, authorId, timeout, notes))

            errorMessage = "Not enough chips!"
            self.con.execute("""
                UPDATE players SET currentChips = (
                    (
                        SELECT currentChips FROM players WHERE playerId = :playerId
                    ) - :bet
                ),
                totalChips = (
                    (
                        SELECT totalChips FROM players WHERE playerId = :playerId
                    ) - :bet
                )
                WHERE playerId = :playerId
            """, {"playerId": authorId, "bet": bet})

            self.con.commit()
            return self.con.execute('SELECT * FROM challenges WHERE messageId = ?;', (messageId,)).fetchone()

        except Exception as e:
            print(e, file=sys.stderr)
            print(f"errorMessage: {errorMessage}", file=sys.stderr, flush=True)
            self.con.rollback()
            if type(e) == ValueError:
                raise e
            else:
                raise ValueError(errorMessage)


    def abortChallenge(self, challengeId, abortedBy):
        
        print(f"aborting challenge with id {challengeId}, by player {abortedBy}", file=sys.stderr, flush=True)

        try:
            challenge = self.con.execute('SELECT * FROM challenges WHERE messageId = ?;', (challengeId,)).fetchone()

            #check status
            if challenge[4] not in [0, 1]:
                print(f"Can't abort game in progress! {challengeId}", file=sys.stderr, flush=True)
                raise ValueError("Can't abort game in progress!")

            if challenge[4] == 1:
                self.con.execute("UPDATE players SET abortedGamesTotal = (SELECT abortedGamesTotal FROM players WHERE playerId = :playerId) + 1 WHERE playerId = :playerId", {"playerId": abortedBy})
            self.con.execute('UPDATE challenges SET status = 4 WHERE messageId = ?', (challengeId,))
            
            # the challenge has been accepted
            if challenge[3] != None:
                data = [challenge[2], challenge[3]]
            else:
                data = [challenge[2]]

            data = [{"playerId": i, "bet": challenge[1]} for i in data]

            self.con.executemany(
                """
                UPDATE players SET currentChips = (
                    (
                        SELECT currentChips FROM players WHERE playerId = :playerId
                    ) + :bet
                ),
                totalChips = (
                    (
                        SELECT totalChips FROM players WHERE playerId = :playerId
                    ) + :bet
                )
                WHERE playerId = :playerId
                """, data
            )

            self.con.commit()

            return self.con.execute('SELECT * FROM challenges WHERE messageId = ?;', (challengeId,)).fetchone()

        except Exception as e:
            print(e, file=sys.stderr, flush=True)
            self.con.rollback()
            if type(e) == ValueError:
                raise e
            else:
                raise ValueError("Something went wrong!")

    def acceptChallenge(self, challengeId, playerId):
        try:
            challenge = self.con.execute("SELECT * from challenges WHERE messageId = ?", (challengeId,)).fetchone()

            if challenge[4] != 0:
                raise ValueError("The challenge is not acceptable!")
            self.con.execute("""
                UPDATE players SET currentChips = (
                    (
                        SELECT currentChips FROM players WHERE playerId = :playerId
                    ) - :bet
                ),
                totalChips = (
                    (
                        SELECT totalChips FROM players WHERE playerId = :playerId
                    ) - :bet
                )
                WHERE playerId = :playerId
            """, {"playerId": playerId, "bet": challenge[1]})

            self.con.execute("UPDATE challenges SET status = 1, acceptedBy = ? WHERE messageId = ?", (playerId, challengeId))
            self.con.commit()

            return self.con.execute('SELECT * FROM challenges WHERE messageId = ?;', (challengeId,)).fetchone()

        except Exception as e:
            print(e, file=sys.stderr, flush=True)
            self.con.rollback()
            if type(e) == ValueError:
                raise e
            else:
                raise ValueError("Something went wrong!")

    def startChallenge(self, challengeId, gameName):
        try:
            challenge = self.con.execute("SELECT * from challenges WHERE messageId = ?", (challengeId,)).fetchone()

            if challenge[4] != 1:
                raise ValueError("The challenge can't be started!")
            
            self.con.execute("UPDATE challenges SET status = 2, gameName = ? WHERE messageId = ?", (gameName, challengeId))
            self.con.commit()

            return self.con.execute('SELECT * FROM challenges WHERE messageId = ?;', (challengeId,)).fetchone()

        except Exception as e:
            print(e, file=sys.stderr, flush=True)
            self.con.rollback()
            if type(e) == ValueError:
                raise e
            else:
                raise ValueError("Something went wrong!")

    def winChallenge(self, challengeId, wonByHost):
        try:
            challenge = self.con.execute("SELECT * from challenges WHERE messageId = ?", (challengeId,)).fetchone()

            if challenge[4] != 2:
                raise ValueError("The challenge can't be ended!")
            
            if wonByHost:
                status = 3
                won = challenge[2]
            else:
                status = 4
                won = challenge[3]

            self.con.execute("UPDATE challenges SET status = ? WHERE messageId = ?", (status, challengeId))
            self.con.execute("""
                UPDATE players SET currentChips = (
                    (
                        SELECT currentChips FROM players WHERE playerId = :playerId
                    ) + :bet
                ),
                totalChips = (
                    (
                        SELECT totalChips FROM players WHERE playerId = :playerId
                    ) + :bet
                )
                WHERE playerId = :playerId
            """, {"playerId": won, "bet": 2*challenge[1]})
            self.con.commit()

            return self.con.execute('SELECT * FROM challenges WHERE messageId = ?;', (challengeId,)).fetchone()

        except Exception as e:
            print(e, file=sys.stderr, flush=True)
            self.con.rollback()
            if type(e) == ValueError:
                raise e
            else:
                raise ValueError("Something went wrong!")

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

    def getChallenge(self, challengeId):
        return self.con.execute('SELECT * FROM challenges WHERE messageId = ?;', (challengeId,)).fetchone()






    def createPlayer(self, playerId):
        errorMessage = "Something went wrong!"
        try:
            errorMessage = "Player is already registered!"
            self.con.execute('INSERT INTO players VALUES (?, 10, 10, 0);', (playerId,))
            self.con.commit()
            return self.con.execute('SELECT * FROM players WHERE playerId = ?', (playerId,)).fetchone()

        except Exception as e:
            if this.MOCK:
                try:
                    self.con.execute('UPDATE players SET currentChips = 10 WHERE playerId = ?;', (playerId,))
                except Exception:
                    pass
            print(e, file=sys.stderr, flush=True)
            self.con.rollback()
            if type(e) == ValueError:
                raise e
            else:
                raise ValueError(errorMessage)

    def getPlayer(self, playerId):
        return self.con.execute('SELECT * FROM players WHERE playerId = ?', (playerId,)).fetchone()

    def getTopPlayersThisEpoch(self, limit=10):
        return self.con.execute('SELECT * FROM players WHERE playerId = ? ORDER BY currentChips LIMIT ?', (playerId, limit)).fetchall()

    def getTopPlayersTotal(self, limit=10):
        return self.con.execute('SELECT * FROM players WHERE playerId = ? ORDER BY totalChips LIMIT ?', (playerId, limit)).fetchall()

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