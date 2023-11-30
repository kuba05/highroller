from enum import Enum

class ChallengeState(Enum):
    PRECREATED = 0
    CREATED = 1
    ACCEPTED = 2
    STARTED = 4
    FINISHED = 5
    ABORTED = 7


GUILD_ID = 447883341463814144

LIST_OF_ADMINS = [
    524276664746639363, # gavlna
    429740472416731147, # espark
    762773913159204894, # sundance
    1110479654306992188, # bot
]
TEAM_ROLES = [
    943876858188005447, # ArticWolves
    943872848257236993, # Plague
    572069501819158528, # Lightning
    572069959476445185, # Ronin
    572069535876775950, # Vikings
    572070907124645919, # Jets
    943160348670820462, # kraken
    572070039113695234, # WF
    630243505629036554, # dragons
]

SPAM_CHANNEL = 1178449202691448942
CHALLENGES_LIST_CHANNEL = 1170686597746917406
RULES_CHANNEL = 1178445726062235649

ACCEPT_EMOJI = "⚔"
ABORT_EMOJI = "❌"
HELPMESSAGE = f"""
See <#{RULES_CHANNEL}> for complete rules.

All commands can be used by sending me the command via DM. Most of them also have a coresponding slash command.

To join our tournament, you will need to use the "register" command.

Then, to create a challenge, use the "create" command. Once someone accepts it (using the "accept" command or by reacting to it in <#{CHALLENGES_LIST_CHANNEL}>), the game will be marked ACCEPTED.
You will get the option to exchange messages with you opponent. You should communicate your in-game names this way and send him the in-game challenge. Once you do, use the "start" command to mark the challenge as ready to start.
Once the challenge finishes, you can claim victory by using the "win" command.

If, at any point, you experience difficulties or technical problems, please let the staff now :D

Other useful commands include:
abort - cancels a game that has not yet been started
help - displays this help message
detailedhelp - displays the uses of all commands

## a syntax for each command is as follows
[command_name] [argument1] [argument2] ...

if an argument has more than one word, you will need to put it inside quotation marks (")
example:
```create 1 "small drylands" "Bardur"```

When a command asks for "challenge" argument, provide the challenge's ID.

When a command asks for "user" argument, provide either the user's ID or their discord name (not server nick).
"""

STARTING_CHIPS=10
SIZES = ["small", "normal"]
SURFACES = ["drylands", "lakes", "continents", "pangea", "archipelago"]
TRIBE_OPTIONS = ["Xin-xi", "Imperius", "Bardur", "Oumaji", "Kickoo", "Hoodrick", "Luxidoor", "Vengir", "Zebasi", "Ai-Mo", "Quetzali", "Yădakk", "Aquarion", "∑∫ỹriȱŋ", "Polaris", "Cymanti"]

MAP_OPTIONS = [size.lower() + " " + surface.lower() for size in SIZES for surface in SURFACES]
