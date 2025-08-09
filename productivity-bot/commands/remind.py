import re
import discord
import uuid

from discord.ext import commands
from database.task_queries import get_user_task, delete_task_cascade, add_task_indexed, get_all_user_tasks
from collections import defaultdict

DAY_MAP = {
    "sun": 0, "sunday": 0,
    "mon": 1, "monday": 1,
    "tue": 2, "tues": 2, "tuesday": 2,
    "wed": 3, "wednesday": 3,
    "thu": 4, "thur": 4, "thurs": 4, "thursday": 4,
    "fri": 5, "friday": 5,
    "sat": 6, "saturday": 6,
}

# Add near your DAY_MAP / helpers
DAY_ORDER = ["sun","mon","tue","wed","thu","fri","sat"]
DAY_ABBR  = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"]

def hhmm(reminder_time) -> str:
    # Works for cassandra.util.Time and datetime.time
    return str(reminder_time)[:5] if reminder_time else "N/A"

def normalize_day_token(tok: str) -> str | None:
    t = tok.strip().lower()
    if not t:
        return None
    
    for k in DAY_MAP.keys():
        if t == k:
            return k
    return None

def expand_day_range(a: str, b: str) -> list[int]:
    """Expand ranges like mon-fri (wrap not supported: sun-wed works; wed-mon is treated as wed..sun)."""
    ai = DAY_ORDER.index(a)
    bi = DAY_ORDER.index(b)
    if ai <= bi:
        seq = DAY_ORDER[ai:bi+1]
    else:
        seq = DAY_ORDER[ai:] + DAY_ORDER[:bi+1]
    return [DAY_MAP[s] for s in seq]

def parse_multi_days(s: str) -> list[int]:
    """
    Parse 'mon,wed,fri' or 'mon wed' or 'mon-wed, fri' into list of DOW ints [0..6] (Sun=0).
    """
    parts = []
    for chunk in s.replace(",", " ").split():
        parts.append(chunk)

    dows: set[int] = set()
    i = 0
    while i < len(parts):
        tok = parts[i]
        if "-" in tok:
            a_raw, b_raw = tok.split("-", 1)
            a = normalize_day_token(a_raw)
            b = normalize_day_token(b_raw)
            if a is None or b is None:
                raise ValueError(f"Invalid day range: {tok}")
            for d in expand_day_range(a, b):
                dows.add(d)
            i += 1
        else:
            k = normalize_day_token(tok)
            if k is None:
                raise ValueError(f"Invalid day: {tok}")
            dows.add(DAY_MAP[k])
            i += 1

    return sorted(dows)


def parse_time_str(time_str: str) -> tuple[int, int]:
    s = time_str.strip().lower()

    m24 = re.fullmatch(r'([01]?\d|2[0-3]):([0-5]\d)', s)
    if m24:
        return int(m24.group(1)), int(m24.group(2))

    m12 = re.fullmatch(r'(1[0-2]|0?\d):([0-5]\d)\s*(am|pm)', s)
    if m12:
        hour = int(m12.group(1))
        minute = int(m12.group(2))
        mer = m12.group(3)
        if mer == "pm" and hour != 12:
            hour += 12
        if mer == "am" and hour == 12:
            hour = 0
        return hour, minute

    raise ValueError("Invalid time. Use HH:MM or h:mmAM/PM (e.g. 09:00, 7:30am).")

def dow_to_human(dow: int | None) -> str:
    names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    return names[dow] if dow is not None and 0 <= dow <= 6 else "Daily"

class Remind(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="remind", help="Add a reminder.\nUsage: !remind daily <time> <task name>\n       !remind weekly <day> <time> <task name>")
    async def remind(self, ctx: commands.Context, freq: str, arg2: str, arg3: str | None = None, *, task_name: str | None = None):
        """
        daily: !remind daily 09:00 Write journal
        weekly: !remind weekly mon 7:30am Standup
        """
        freq_norm = freq.strip().lower()
        user_id = str(ctx.author.id)

        try:
            if freq_norm == "daily":
                if task_name is None:
                    time_str = arg2
                    task = (arg3 or "").strip()
                    if not task:
                        raise ValueError("Missing task name.")
                else:
                    time_str = arg2
                    task = task_name
                hour, minute = parse_time_str(time_str)
                task_id = add_task_indexed(
                    user_id=user_id,
                    task_name=task,
                    description=None,
                    reminder_type="daily",
                    reminder_hour=hour,
                    reminder_minute=minute,
                    day_of_week=None,
                )
                await ctx.send(f"✅ {ctx.author.mention} daily reminder set for **{task}** at **{arg2}** (task_id `{task_id}`)")

            elif freq_norm == "weekly":
                if arg3 is None or task_name is None:
                    raise ValueError("Usage: !remind weekly <days> <time> <task name> (e.g., mon,wed or mon-fri)")
                day_expr = arg2.strip()
                try:
                    dows = parse_multi_days(day_expr)
                except ValueError as e:
                    raise ValueError(str(e) + "  Try: mon,wed or mon-fri")

                if not dows:
                    raise ValueError("No valid days provided. Try: mon,wed or mon-fri")

                hour, minute = parse_time_str(arg3)
                task = task_name

                created_ids = []
                for dow in dows:
                    tid = add_task_indexed(
                        user_id=user_id,
                        task_name=task,
                        description=None,
                        reminder_type="weekly",
                        reminder_hour=hour,
                        reminder_minute=minute,
                        day_of_week=dow,
                    )
                    created_ids.append(str(tid))

                days_human = ", ".join(DAY_ABBR[d] for d in dows)
                await ctx.send(
                    f"✅ {ctx.author.mention} weekly reminders set for **{task}** on **{days_human} {arg3}**\n"
                    f"🆔 " + ", ".join(f"`{tid}`" for tid in created_ids)
                )
            else:
                raise ValueError("Frequency must be 'daily' or 'weekly'.")
        except ValueError as e:
            await ctx.send(f"⚠ {ctx.author.mention} {e}")

    @commands.command(name="list", help="List your reminders")
    async def list(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        rows = get_all_user_tasks(user_id)

        if not rows:
            await ctx.send(f"✅ {ctx.author.mention} you have no active reminders.")
            return

        groups = defaultdict(lambda: {"days": set(), "task_ids": [], "time": "N/A", "type": "Unknown"})
        for r in rows:
            time_str = hhmm(getattr(r, "reminder_time", None))
            rtype = (r.reminder_type or "unknown").lower()
            key = (r.task_name, time_str, rtype)
            g = groups[key]
            g["time"] = time_str
            g["type"] = rtype
            g["task_ids"].append(str(r.task_id))
            if rtype == "weekly":
                dow = getattr(r, "reminder_day_of_week", None)
                if isinstance(dow, int) and 0 <= dow <= 6:
                    g["days"].add(dow)

        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Reminders",
            description="(Weekly tasks on multiple days are collapsed)",
        )

        def sort_key(item):
            (name, time_str, rtype) = item[0]
            try:
                h, m = map(int, time_str.split(":"))
            except Exception:
                h, m = (99, 99)
            return (0 if rtype == "daily" else 1, h, m, name.lower())

        for (name, time_str, rtype), info in sorted(groups.items(), key=sort_key):
            if rtype == "weekly" and info["days"]:
                days_human = ", ".join(DAY_ABBR[d] for d in sorted(info["days"]))
                when = f"{days_human} {time_str}"
                freq_label = "Weekly"
            else:
                when = time_str
                freq_label = "Daily" if rtype == "daily" else rtype.capitalize()

            ids_str = ", ".join(f"`{tid}`" for tid in info["task_ids"])

            embed.add_field(
                name=name,
                value=f"⏰ {when} — {freq_label}\n🆔 {ids_str}",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command(
        name="delete",
        help="Delete a reminder by task_id. Usage: !delete <task_id>"
    )
    async def delete(self, ctx: commands.Context, task_id_str: str):
        user_id = str(ctx.author.id)

        try:
            task_id = uuid.UUID(task_id_str)
        except ValueError:
            await ctx.send(f"⚠ {ctx.author.mention} invalid task_id. Paste the one shown when you created the reminder.")
            return

        row = get_user_task(user_id, task_id)
        if not row:
            await ctx.send(f"⚠ {ctx.author.mention} task not found for your account.")
            return

        reminder_type = getattr(row, "reminder_type", None)
        reminder_time = getattr(row, "reminder_time", None)
        day_of_week = getattr(row, "reminder_day_of_week", None)
        task_name = getattr(row, "task_name", str(task_id))

        if reminder_type is None or reminder_time is None:
            await ctx.send(f"⚠ {ctx.author.mention} this task has no reminder info; nothing to delete.")
            return

        hour = reminder_time.hour
        minute = reminder_time.minute

        try:
            delete_task_cascade(
                user_id=user_id,
                task_id=task_id,
                reminder_type=reminder_type,
                reminder_hour=hour,
                reminder_minute=minute,
                day_of_week=day_of_week if day_of_week != -1 else None
            )
        except Exception as e:
            await ctx.send(f"❌ {ctx.author.mention} failed to delete reminder: {e}")
            return

        parsed_when = (
            f"{dow_to_human(day_of_week)} {hour:02}:{minute:02}"
            if reminder_type == "weekly" and isinstance(day_of_week, int) and 0 <= day_of_week <= 6
            else f"{hour:02}:{minute:02}"
        )
        await ctx.send(f"🗑️ {ctx.author.mention} deleted reminder **{task_name}** ({reminder_type}, {parsed_when}).")

async def setup(bot: commands.Bot):
    await bot.add_cog(Remind(bot))
