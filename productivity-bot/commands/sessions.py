import uuid

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo
from discord.ext import commands
from database.task_queries import get_all_user_tasks, get_user_task
from database.active_task_queries import (
    get_active_user_task,
    add_active_user_task,
    delete_active_user_task,
)
from database.session_queries import add_session_for_task
from database.daily_remaining_queries import remove_from_today

EST = ZoneInfo("America/Toronto")
def now_est():
    return datetime.now(EST)

def as_est(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(EST)

def try_parse_uuid(s: str) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(s)
    except Exception:
        return None

def find_task_for_user_by_name(user_id_text: str, name: str):
    for row in get_all_user_tasks(user_id_text):
        if row.task_name.lower() == name.lower():
            return row
    return None

class Sessions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(
        name="start",
        help="Start working on a task. Usage: !start <task_id | exact task name>"
    )
    async def start(self, ctx: commands.Context, *, task_ref: str):
        user_id_text = str(ctx.author.id)

        # Resolve task: by UUID first, then by exact name
        task_row = None
        tid = try_parse_uuid(task_ref.strip())
        if tid:
            task_row = get_user_task(user_id_text, tid)
            if not task_row:
                await ctx.send(f"⚠ {ctx.author.mention} task_id not found for your account.")
                return
        else:
            task_row = find_task_for_user_by_name(user_id_text, task_ref.strip())
            if not task_row:
                await ctx.send(f"⚠ {ctx.author.mention} no task named **{task_ref}** found. Use `!remindlist` to see your tasks.")
                return
            tid = task_row.task_id

        # Check if user already has an active task
        current = get_active_user_task(user_id_text)
        now = now_est()

        if current:
            if current.task_id == tid:
                await ctx.send(f"✅ {ctx.author.mention} you're already working on **{task_row.task_name}** (started at {current.start_time}).")
                return
            else:
                # Auto-stop previous active task
                prev_start = as_est(current.start_time)
                duration_hours = max((now - prev_start).total_seconds() / 3600.0, 0.0)
                add_session_for_task(user_id_text, current.task_id, prev_start, now, duration_hours)
                delete_active_user_task(user_id_text)

        # Start new active session
        remove_from_today(user_id_text, tid)
        add_active_user_task(user_id_text, tid, now)
        await ctx.send(f"▶️ {ctx.author.mention} started **{task_row.task_name}** at {now.strftime('%H:%M %p')} EST.")

    @commands.command(
        name="stop",
        help="Stop your active task and record a session. Usage: !stop"
    )
    async def stop(self, ctx: commands.Context):
        user_id_text = str(ctx.author.id)
        current = get_active_user_task(user_id_text)

        if not current:
            await ctx.send(f"⚠ {ctx.author.mention} you don't have an active task. Use `!start <task_id|name>`.")
            return

        now = now_est()
        start_time = as_est(current.start_time)
        duration_hours = max((now - start_time).total_seconds() / 3600.0, 0.0)

        task_row = get_user_task(user_id_text, current.task_id)
        task_name = getattr(task_row, "task_name", str(current.task_id))
        add_session_for_task(user_id_text, current.task_id, start_time, now, duration_hours)
        delete_active_user_task(user_id_text)

        await ctx.send(
            f"⏹️ {ctx.author.mention} stopped **{task_name}**. Logged **{duration_hours:.2f}h** "
            f"(from {start_time.strftime('%H:%M %p')} to {now.strftime('%H:%M %p')} EST)."
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Sessions(bot))
