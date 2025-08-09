from datetime import time as dtime
from zoneinfo import ZoneInfo
from discord.ext import tasks
from database.daily_remaining_queries import seed_today_from_reminders

TZ = ZoneInfo("America/Toronto")

@tasks.loop(time=dtime(hour=13, minute=49, tzinfo=TZ))
async def seed_daily_lists():
    seed_today_from_reminders()
    print("Seeded today's daily task lists.")

def start_seed_task(bot):
    seed_daily_lists.bot = bot
    seed_daily_lists.start()