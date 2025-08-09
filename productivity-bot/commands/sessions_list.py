import uuid

from datetime import datetime, timedelta, timezone
from typing import Optional, List
from discord.ext import commands
from zoneinfo import ZoneInfo
from database.task_queries import get_all_user_tasks, get_user_task
from database.session_queries import get_sessions_for_user_task_range

EST = ZoneInfo("America/Toronto")

def now_est() -> datetime:
    return datetime.now(EST)

def as_est(dt: datetime) -> datetime:
    """Convert naive UTC datetime (from Cassandra) to EST aware."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(EST)

def try_parse_uuid(s: str) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(s)
    except Exception:
        return None

def resolve_task_for_user(user_id_text: str, task_ref: str):
    tid = try_parse_uuid(task_ref.strip())
    if tid:
        return get_user_task(user_id_text, tid)
    ref_lower = task_ref.strip().lower()
    for row in get_all_user_tasks(user_id_text):
        if row.task_name and row.task_name.lower() == ref_lower:
            return row
    return None

class SessionsList(commands.Cog):
    """List work sessions for the past 24h or week, plus a total."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(
        name="sessions",
        help="List your sessions in the past 24h or week (with a total).\n"
             "Usage: !sessions [24h|week] [optional task name or task_id]\n"
             "Examples:\n"
             "  !sessions\n"
             "  !sessions week\n"
             "  !sessions 24h \"Write journal\""
    )
    async def sessions_cmd(self, ctx: commands.Context, period: Optional[str] = None, *, task_ref: Optional[str] = None):
        user_id = str(ctx.author.id)
        period_norm = (period or "24h").lower()

        if period_norm not in ("24h", "week"):
            await ctx.send(f"⚠ {ctx.author.mention} period must be '24h' or 'week'.")
            return

        now_est = now_est()
        start_est = now_est - (timedelta(hours=24) if period_norm == "24h" else timedelta(days=7))
        start_utc = start_est.astimezone(timezone.utc).replace(tzinfo=None)
        end_utc   = now_est.astimezone(timezone.utc).replace(tzinfo=None)

        sessions_data: List[tuple[str, datetime, datetime, float]] = []
        total_hours = 0.0

        if task_ref:
            # Single task
            task_row = resolve_task_for_user(user_id, task_ref)
            if not task_row:
                await ctx.send(f"⚠ {ctx.author.mention} I couldn't find a task matching **{task_ref}**.")
                return
            sessions = get_sessions_for_user_task_range(user_id, task_row.task_id, start_from=start_utc, end_before=end_utc)
            for s in sessions:
                start = as_est(s.start_time)
                end   = as_est(s.end_time)
                dur   = float(getattr(s, "duration_hours", 0.0) or 0.0)
                total_hours += dur
                sessions_data.append((task_row.task_name, start, end, dur))
        else:
            # All tasks
            for t in get_all_user_tasks(user_id):
                sessions = get_sessions_for_user_task_range(user_id, t.task_id, start_from=start_utc, end_before=end_utc)
                for s in sessions:
                    start = as_est(s.start_time)
                    end   = as_est(s.end_time)
                    dur   = float(getattr(s, "duration_hours", 0.0) or 0.0)
                    total_hours += dur
                    sessions_data.append((t.task_name, start, end, dur))

        if not sessions_data:
            await ctx.send(f"✅ {ctx.author.mention} no sessions in the past {period_norm}.")
            return

        # Sort by start time descending
        sessions_data.sort(key=lambda x: x[1], reverse=True)

        # Build output with total at the bottom
        header = f"🗓️ {ctx.author.mention} — sessions in past {period_norm}:"
        lines = [header]
        for name, start, end, dur in sessions_data:
            lines.append(
                f"• **{name}** — {start.strftime('%Y-%m-%d %I:%M %p')} → {end.strftime('%I:%M %p')} ({dur:.2f}h)"
            )
        lines.append(f"**Total ({period_norm})**: **{total_hours:.2f}h**")

        # Send, respecting 2000-char limit
        msg = "\n".join(lines)
        if len(msg) <= 2000:
            await ctx.send(msg)
        else:
            # Chunking: keep header on first message; ensure total is on the last one
            chunks: List[str] = []
            current = header
            for line in lines[1:-1]:  # all but header and total
                if len(current) + 1 + len(line) > 1900:
                    chunks.append(current)
                    current = line
                else:
                    current += "\n" + line
            # append last chunk (with total)
            final_chunk = current + "\n" + lines[-1]
            chunks.append(final_chunk)
            for chunk in chunks:
                await ctx.send(chunk)

async def setup(bot: commands.Bot):
    await bot.add_cog(SessionsList(bot))
