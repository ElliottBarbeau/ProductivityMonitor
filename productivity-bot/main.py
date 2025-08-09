import logging
import os
import discord
import asyncio

from pathlib import Path
from discord.ext import commands
from dotenv import load_dotenv, find_dotenv
from database.table_queries import table_exists
from database.reminder_queries import create_reminders_table
from database.active_task_queries import create_active_tasks_table
from database.session_queries import create_sessions_table
from database.task_queries import create_tasks_table
from tasks.remind_scheduler import start_monitor
from tasks.daily_digest import start_daily_digest

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
    command_prefix = "!",
    intents = intents,
    help_command = commands.MinimalHelpCommand(),
    activity = discord.Game(name = "with 🦥 in Costa Rica"),
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
    CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE")
    REMIND_TABLE = "reminders_by_time"

    if not table_exists(CASSANDRA_KEYSPACE, REMIND_TABLE):
        create_tasks_table()
        create_active_tasks_table()
        create_reminders_table()
        create_sessions_table()

    start_monitor(bot)
    start_daily_digest(bot)
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
    await load_cogs()
    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())