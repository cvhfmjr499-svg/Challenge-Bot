import os

# Tests always run against the challenge config, never a second account selected by the shell.
os.environ.pop("BOT_STATE", None)
os.environ.pop("BOT_CONFIG", None)
