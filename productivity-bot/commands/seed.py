import logging

from discord.ext import commands
from tasks.daily_seed import seed_daily_lists

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="seed")
    async def seed(self, ctx):
        seed_daily_lists()
        await ctx.send("Daily tasks seeded")


async def setup(bot):
    logging.info("Running AdminCommands cog setup()")
    await bot.add_cog(AdminCommands(bot))