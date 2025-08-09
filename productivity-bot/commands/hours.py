# commands/sessions.py  (append to the existing Sessions cog)
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import discord
from discord.ext import commands

from database.task_queries import get_all_user_tasks
from database.session_queries import get_sessions_for_user_task_range

EST = ZoneInfo("America/Toronto")
def _now_est() -> datetime:
    return datetime.now(EST)

def _window_bounds_utc(scope: str) -> tuple[datetime | None, datetime | None]:
    now_est = _now_est()
    scope = (scope or "week").lower()
    if scope in ("week", "w"):
        start_est = now_est - timedelta(days=7)
    elif scope in ("month", "m"):
        start_est = now_est - timedelta(days=30)
    elif scope in ("year", "y"):
        start_est = now_est - timedelta(days=365)
    elif scope in ("all", "a", "overall"):
        return (None, None)
    else:
        start_est = now_est - timedelta(days=7)

    start_utc = start_est.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = now_est.astimezone(timezone.utc).replace(tzinfo=None)
    return (start_utc, end_utc)

class Sessions(commands.Cog):
    @commands.command(
        name="hours",
        help="Show total hours in an optional time frame. Usage: !hours [week|month|year|all]"
    )
    async def hours(self, ctx: commands.Context, scope: str | None = None):
        user_id = str(ctx.author.id)
        start_utc, end_utc = _window_bounds_utc(scope)

        tasks_rows = get_all_user_tasks(user_id)
        if not tasks_rows:
            await ctx.send(f"✅ {ctx.author.mention} you have no tasks yet.")
            return

        per_task = []
        total_hours = 0.0

        for t in tasks_rows:
            task_hours = 0.0
            if start_utc and end_utc:
                sessions = get_sessions_for_user_task_range(user_id, t.task_id, start_from=start_utc, end_before=end_utc)
            else:
                sessions = get_sessions_for_user_task_range(user_id, t.task_id)

            for s in sessions:
                dh = getattr(s, "duration_hours", 0.0) or 0.0
                task_hours += float(dh)

            if task_hours > 0:
                per_task.append((t.task_name, task_hours))
                total_hours += task_hours

        label = (scope or "week").lower()
        if label in ("w",): label = "week"
        if label in ("m",): label = "month"
        if label in ("y",): label = "year"
        if label in ("a", "overall"): label = "all"

        if total_hours <= 0.0:
            await ctx.send(f"⏱️ {ctx.author.mention} total hours in **{label}**: **0.00h**")
            return

        per_task.sort(key=lambda x: x[1], reverse=True)
        lines = [f"**Total ({label})**: **{total_hours:.2f}h**"]
        for name, h in per_task[:10]:
            lines.append(f"• {name}: {h:.2f}h")

        if len(per_task) > 10:
            others = len(per_task) - 10
            lines.append(f"... and {others} more task(s).")

        await ctx.send(f"⏱️ {ctx.author.mention}\n" + "\n".join(lines))
