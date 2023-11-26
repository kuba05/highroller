from enum import Enum

class ChallengeState(Enum):
    PRECREATED = 0
    CREATED = 1
    ACCEPTED = 2
    STARTED = 4
    FINISHED = 5
    ABORTED = 7



ACCEPT_EMOJI = "⚔"
ABORT_EMOJI = "❌"
HELPMESSAGE = f"""TODO"""

STARTING_CHIPS=10
SIZES = ["small", "normal", "large", "huge"]
SURFACES = ["drylands", "lakes", "continents"]
TRIBE_OPTIONS = ["Xin-xi", "Imperius", "Bardur", "Oumaji", "Kickoo", "Hoodrick", "Luxidoor", "Vengir", "Zebasi", "Ai-Mo", "Quetzali", "Yădakk", "Aquarion", "∑∫ỹriȱŋ", "Polaris", "Cymanti"]

MAP_OPTIONS = [size + " " + surface for size in SIZES for surface in SURFACES]

LIST_OF_ADMINS = [524276664746639363, 429740472416731147]
GUILD_ID = 447883341463814144