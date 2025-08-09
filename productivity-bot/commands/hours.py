# commands/hours.py
import uuid
from typing import Optional, Tuple, List

import discord
from discord.ext import commands

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from database.task_queries import get_all_user_tasks, get_user_task
from database.session_queries import get_sessions_for_user_task_range

# Bot-wide timezone (Eastern with DST)
EST = ZoneInfo("America/Toronto")

def now_est() -> datetime:
    return datetime.now(EST)

def window_bounds_utc(scope):
    label_map = {"w":"week","week":"week",
                 "m":"month","month":"month",
                 "y":"year","year":"year",
                 "a":"all","all":"all","overall":"all"}
    label = label_map.get((scope or "week").lower(), "week")

    if label == "all":
        return None, None, label

    _now_est = now_est()
    if label == "week":
        start_est = _now_est - timedelta(days=7)
    elif label == "month":
        start_est = _now_est - timedelta(days=30)
    else:
        start_est = _now_est - timedelta(days=365)

    start_utc = start_est.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = _now_est.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc, label

def try_parse_uuid(s: str) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(s)
    except Exception:
        return None

def resolve_task_for_user(user_id_text: str, task_ref: str):
    tid = try_parse_uuid(task_ref.strip())
    if tid:
        return get_user_task(user_id_text, tid)
    for row in get_all_user_tasks(user_id_text):
        if row.task_name and row.task_name.lower() == task_ref.strip().lower():
            return row
    return None

class Hours(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(
        name="hours",
        help="Show total hours in an optional timeframe and task.\n"
             "Usage: !hours [week|month|year|all] [optional task name or task_id]\n"
    )
    async def hours(self, ctx: commands.Context, scope: Optional[str] = None, *, task_ref: Optional[str] = None):
        user_id = str(ctx.author.id)

        start_utc, end_utc, label = window_bounds_utc(scope)

        if task_ref:
            task_row = resolve_task_for_user(user_id, task_ref)
            if not task_row:
                await ctx.send(f"⚠ {ctx.author.mention} I couldn't find a task matching **{task_ref}**. "
                               f'Use `!remindlist` to see your tasks.')
                return

            if start_utc and end_utc:
                sessions = get_sessions_for_user_task_range(user_id, task_row.task_id,
                                                            start_from=start_utc, end_before=end_utc)
            else:
                sessions = get_sessions_for_user_task_range(user_id, task_row.task_id)

            task_hours = sum(float(getattr(s, "duration_hours", 0.0) or 0.0) for s in sessions)
            await ctx.send(f"⏱️ {ctx.author.mention} **{task_row.task_name}** — total ({label}): **{task_hours:.2f}h**")
            return

        tasks_rows = get_all_user_tasks(user_id)
        if not tasks_rows:
            await ctx.send(f"✅ {ctx.author.mention} you have no tasks yet.")
            return

        per_task: List[Tuple[str, float]] = []
        total_hours = 0.0

        for t in tasks_rows:
            if start_utc and end_utc:
                sessions = get_sessions_for_user_task_range(user_id, t.task_id,
                                                            start_from=start_utc, end_before=end_utc)
            else:
                sessions = get_sessions_for_user_task_range(user_id, t.task_id)
            task_hours = sum(float(getattr(s, "duration_hours", 0.0) or 0.0) for s in sessions)
            if task_hours > 0:
                per_task.append((t.task_name, task_hours))
                total_hours += task_hours

        if total_hours <= 0.0:
            await ctx.send(f"⏱️ {ctx.author.mention} total hours in **{label}**: **0.00h**")
            return

        per_task.sort(key=lambda x: x[1], reverse=True)
        lines = [f"**Total ({label})**: **{total_hours:.2f}h**"]
        for name, h in per_task[:10]:
            lines.append(f"• {name}: {h:.2f}h")
        if len(per_task) > 10:
            lines.append(f"... and {len(per_task) - 10} more task(s).")

        await ctx.send(f"⏱️ {ctx.author.mention}\n" + "\n".join(lines))

async def setup(bot: commands.Bot):
    await bot.add_cog(Hours(bot))
