# tasks/daily_digest.py
import os
from collections import defaultdict
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import discord
from discord.ext import tasks
from cassandra.query import SimpleStatement

from database.cassandra_client import session
from database.task_queries import get_user_task
from database.reminder_queries import fetch_due_today_user_task_ids

# Config / timezone
TZ = ZoneInfo("America/Toronto")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
DAILY_SENTINEL_DOW = -1  # as per your schema: daily = -1

def today_dow_sunday0(now_local: datetime) -> int:
    return (now_local.weekday() + 1) % 7

async def send_user_digest(bot: discord.Client, user_id: str, task_rows: list[object]):
    """
    Send an embed digest for a single user listing today's tasks.
    task_rows are rows from tasks_by_user (we fetch names & times there).
    """
    if not CHANNEL_ID:
        return
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return

    # Build embed
    today_str = datetime.now(TZ).strftime("%Y-%m-%d")
    embed = discord.Embed(
        title=f"Today's Tasks — {today_str}",
        description="Here are your tasks scheduled for today:",
        color=discord.Color.blurple(),
    )

    # Add task fields (time from tasks_by_user.reminder_time)
    for r in task_rows:
        # reminder_time is CQL 'time' (cassandra.util.Time) or datetime.time -> show HH:MM
        time_str = "N/A"
        if getattr(r, "reminder_time", None) is not None:
            time_str = str(r.reminder_time)[:5]  # "HH:MM"
        freq = (r.reminder_type or "unknown").capitalize()
        embed.add_field(
            name=r.task_name,
            value=f"⏰ {time_str} — {freq}",
            inline=False
        )

    # Mention in plain content so it notifies the user
    try:
        user = await bot.fetch_user(int(user_id))
        mention = user.mention if user else f"<@{user_id}>"
    except Exception:
        mention = f"<@{user_id}>"

    await channel.send(content=f"{mention} — your daily task digest:", embed=embed)

async def gather_task_rows_for_user(user_id: str, task_ids: set) -> list[object]:
    """
    Fetch the tasks_by_user rows for display (name, time, type).
    """
    out = []
    for tid in task_ids:
        row = get_user_task(user_id, tid)
        if row:
            out.append(row)
    def _key(r):
        t = getattr(r, "reminder_time", None)
        if t is None:
            return (99, 99)
        try:
            return (t.hour, t.minute) 
        except Exception:
            s = str(t)[:5]
            try:
                h, m = map(int, s.split(":"))
                return (h, m)
            except Exception:
                return (99, 99)
    out.sort(key=_key)
    return out

# Schedule at 1pm
@tasks.loop(time=dtime(hour=13, tzinfo=TZ))
async def daily_task_digest():
    bot = daily_task_digest.bot
    now_local = datetime.now(TZ)

    by_user_taskids = fetch_due_today_user_task_ids(now_local)

    for user_id, task_ids in by_user_taskids.items():
        if not task_ids:
            continue
        task_rows = await gather_task_rows_for_user(user_id, task_ids)
        if task_rows:
            await send_user_digest(bot, user_id, task_rows)

def start_daily_digest(bot: discord.Client | discord.ext.commands.Bot):
    daily_task_digest.bot = bot
    daily_task_digest.start()
    print("Daily digest scheduled (1pm America/Toronto).")
