from discord.ext import commands
from database.daily_remaining_queries import list_remaining_today

class Daily(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(
        name="daily",
        help="Show your remaining tasks for today (based on your reminders)."
    )
    async def daily(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        rows = list_remaining_today(user_id)
        if not rows:
            await ctx.send(f"{ctx.author.mention} you completed all of your tasks for today. Nice job!")
            return

        # Keep it simple, copy-paste friendly (includes task_id)
        lines = [f"📝 {ctx.author.mention} today's remaining tasks:"]
        for r in rows:
            lines.append(f"• **{r.task_name}** — `task_id: {r.task_id}`")
        await ctx.send("\n".join(lines))

async def setup(bot: commands.Bot):
    await bot.add_cog(Daily(bot))
