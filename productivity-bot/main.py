import logging
import os
import discord
import asyncio

from pathlib import Path
from discord.ext import commands
from dotenv import load_dotenv, find_dotenv
from time import sleep

'''
TODO:

db table for daily tasks, flag, and days to repeat
db table for hours tracked on which task, how many hours in each month

'''

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = ".env"
COGS_PACKAGE = "commands"
COGS_PATH = BASE_DIR / COGS_PACKAGE

# Load .env from: local dir, parent dir, or search upwards from CWD
candidates = [BASE_DIR / ENV_FILE, BASE_DIR.parent / ENV_FILE]
loaded = False
for p in candidates:
    if p.is_file():
        load_dotenv(p)
        loaded = True
        break

if not loaded:
    # fallback: search from current working directory upward
    dp = find_dotenv(usecwd=True)
    if dp:
        load_dotenv(dp)
        loaded = True

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN is None:
    raise RuntimeError("DISCORD_TOKEN not found in env file.")

# Initialize logging
logging.basicConfig(
    level = logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Initialize bot
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(
    command_prefix = "$",
    intents = intents,
    help_command = commands.MinimalHelpCommand(),
    activity = discord.Game(name = "with Python 🐍"),
    case_insensitive=True
)

# Cog loader
async def load_cogs():
    for file in COGS_PATH.iterdir():
        if not file.name.startswith("_") and file.name.endswith(".py"):
            ext = f"{COGS_PACKAGE}.{file.stem}"  # e.g. "commands.buy"
            try:
                await bot.load_extension(ext)
                logging.info("Loaded extension: %s", ext)
            except commands.ExtensionAlreadyLoaded:
                logging.warning("Extension %s already loaded", ext)
            except Exception as exc:
                logging.exception("Failed to load %s: %s", ext, exc)

# Global events
@bot.event
async def on_ready():
    print("All commands:", sorted(bot.all_commands.keys()))
    logging.info(
        "Logged in as %s (ID: %s). Connected to %d guild(s).",
        bot.user,
        bot.user.id,
        len(bot.guilds),
    )

# Error handling
@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return
    
    logging.error("Error in command %s: %s", ctx.command.cog_name, error)
    await ctx.reply(f"Oops! An error occured", mention_author=False)
    

async def main() -> None:
    # Change this
    await load_cogs()
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())