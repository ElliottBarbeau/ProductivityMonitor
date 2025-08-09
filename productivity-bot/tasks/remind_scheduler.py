import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from discord.ext import tasks
import discord
from datetime import datetime, timedelta
from database.reminder_queries import get_daily_window, get_weekly_window
from database.task_queries import get_user_task

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = ".env"

# Load env
candidates = [BASE_DIR / ENV_FILE, BASE_DIR.parent / ENV_FILE]
loaded = False
for p in candidates:
    if p.is_file():
        load_dotenv(p)
        loaded = True
        break
if not loaded:
    dp = find_dotenv(usecwd=True)
    if dp:
        load_dotenv(dp)
        loaded = True

CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# Track sent reminders in memory for de-duplication
sent_recently = {}  # {(user_id, task_id): last_sent_datetime}

# How long to keep entries in sent_recently before allowing another ping
DEDUP_WINDOW_MINUTES = 15

async def ping_user(bot, user_id, task_name):
    user = await bot.fetch_user(user_id)
    if not user:
        return

    channel = bot.get_channel(CHANNEL_ID)
    embed = discord.Embed(
        title="⏰ Reminder",
        description=f"Hey {user.mention}, it's time for your task: **{task_name}**!",
        color=discord.Color.green()
    )

    await channel.send(embed=embed)

async def check_reminders(bot):
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    current_day_of_week = (now.weekday() + 1) % 7

    cutoff = now - timedelta(minutes=DEDUP_WINDOW_MINUTES)
    for key, last_sent in list(sent_recently.items()):
        if last_sent < cutoff:
            del sent_recently[key]

    daily_reminders = get_daily_window(current_hour, current_minute, current_minute + 5)
    for reminder in daily_reminders:
        key = (reminder.user_id, reminder.task_id)
        if key in sent_recently:
            continue
        task = get_user_task(reminder.user_id, reminder.task_id)
        if task:
            await ping_user(bot, reminder.user_id, task.task_name)
            sent_recently[key] = now

    weekly_reminders = get_weekly_window(current_day_of_week, current_hour, current_minute, current_minute + 5)
    for reminder in weekly_reminders:
        key = (reminder.user_id, reminder.task_id)
        if key in sent_recently:
            continue
        task = get_user_task(reminder.user_id, reminder.task_id)
        if task:
            await ping_user(bot, reminder.user_id, task.task_name)
            sent_recently[key] = now

@tasks.loop(minutes=1)
async def monitor_reminders():
    await check_reminders(monitor_reminders.bot)

def start_monitor(bot):
    monitor_reminders.bot = bot
    monitor_reminders.start()
    print("Reminder monitor running.")
