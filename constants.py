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
SIZES = ["small", "normal"]
SURFACES = ["drylands", "lakes", "continents", "pangea", "archipelago"]
TRIBE_OPTIONS = ["Xin-xi", "Imperius", "Bardur", "Oumaji", "Kickoo", "Hoodrick", "Luxidoor", "Vengir", "Zebasi", "Ai-Mo", "Quetzali", "Yădakk", "Aquarion", "∑∫ỹriȱŋ", "Polaris", "Cymanti"]

MAP_OPTIONS = [size + " " + surface for size in SIZES for surface in SURFACES]

LIST_OF_ADMINS = [524276664746639363, 429740472416731147, 1110479654306992188]
GUILD_ID = 447883341463814144
CHALLENGES_LIST_CHANNEL = 1170686597746917406
SPAM_CHANNEL = 1170686597746917406

TEAM_ROLES = [572070039113695234, 943876858188005447, 630243505629036554]