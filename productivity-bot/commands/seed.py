import logging

from discord.ext import commands
from tasks.daily_seed import seed_daily_lists

class Seed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="seed")
    async def seed(self, ctx):
        await seed_daily_lists()
        await ctx.send("Daily tasks seeded.")


async def setup(bot):
    logging.info("Running Seed cog setup()")
    await bot.add_cog(Seed(bot))