import re
import discord
import uuid

from discord.ext import commands
from database.task_queries import get_user_task, delete_task_cascade, add_task_indexed, get_all_user_tasks

DAY_MAP = {
    "sun": 0, "sunday": 0,
    "mon": 1, "monday": 1,
    "tue": 2, "tues": 2, "tuesday": 2,
    "wed": 3, "wednesday": 3,
    "thu": 4, "thur": 4, "thurs": 4, "thursday": 4,
    "fri": 5, "friday": 5,
    "sat": 6, "saturday": 6,
}

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

        # Parse args according to frequency
        try:
            if freq_norm == "daily":
                if task_name is None:
                    # user used: !remind daily <time> <task>
                    time_str = arg2
                    task = (arg3 or "").strip()
                    if not task:
                        raise ValueError("Missing task name.")
                else:
                    # user used 4+ args; arg2=time, task_name provided by discord parser
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
                # Expect: !remind weekly <day> <time> <task...>
                if arg3 is None or task_name is None:
                    raise ValueError("Usage: !remind weekly <day> <time> <task name>")
                day_key = arg2.strip().lower()
                if day_key not in DAY_MAP:
                    raise ValueError("Invalid day. Try mon, tue, wed, thu, fri, sat, sun.")
                dow = DAY_MAP[day_key]
                hour, minute = parse_time_str(arg3)
                task = task_name
                task_id = add_task_indexed(
                    user_id=user_id,
                    task_name=task,
                    description=None,
                    reminder_type="weekly",
                    reminder_hour=hour,
                    reminder_minute=minute,
                    day_of_week=dow,
                )
                human_day = dow_to_human(dow)
                await ctx.send(f"✅ {ctx.author.mention} weekly reminder set for **{task}** on **{human_day} {arg3}** (task_id `{task_id}`)")
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

        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Reminders",
            description="Your scheduled pings",
        )

        for r in rows:
            # rows include: task_name, reminder_type, reminder_time, reminder_day_of_week, task_id
            time_str = str(r.reminder_time)[:5] if getattr(r, "reminder_time", None) else "N/A"
            freq = (r.reminder_type or "unknown").capitalize()
            dow = getattr(r, "reminder_day_of_week", None)
            when = f"{dow_to_human(dow)} {time_str}" if freq.lower() == "weekly" else time_str

            embed.add_field(
                name=f"{r.task_name}",
                value=(
                    f"⏰ {when} — {freq}\n"
                    f"🆔 `{r.task_id}`"
                ),
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
