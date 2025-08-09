import logging

from discord.ext import commands
from database.cassandra_client import session

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def reset_database(self, ctx):
        tables = [
            "active_tasks_by_user",
            "reminders_by_time",
            "sessions_by_user_task",
            "tasks_by_user",
            "daily_remaining_by_user"
        ]

        try:
            self.bot.initialized = False
            for table in tables:
                session.execute(f"DROP TABLE IF EXISTS {table}")
            
            await ctx.send("⚠️ **All data wiped!** The database is now empty.")
            logging.warning("Database wiped by admin command.")
        except Exception as e:
            await ctx.send(f"Failed to wipe database: {e}")
            logging.error(f"Database wipe failed: {e}")

async def setup(bot):
    logging.info("Running AdminCommands cog setup()")
    await bot.add_cog(AdminCommands(bot))