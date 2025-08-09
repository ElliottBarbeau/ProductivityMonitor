# database/daily_remaining_queries.py
from datetime import datetime
from zoneinfo import ZoneInfo
from cassandra.query import SimpleStatement
from .cassandra_client import session
from .task_queries import get_user_task
from .reminder_queries import DAILY_SENTINEL_DOW

TZ = ZoneInfo("America/Toronto")

def create_daily_remaining_table():
    session.execute("""
        CREATE TABLE IF NOT EXISTS daily_remaining_by_user (
            user_id TEXT,
            date DATE,
            task_id UUID,
            task_name TEXT,
            added_at TIMESTAMP,
            PRIMARY KEY ((user_id, date), task_id)
        ) WITH CLUSTERING ORDER BY (task_id ASC)
    """)

def list_remaining_today(user_id: str):
    today = datetime.now(TZ).date()
    query = SimpleStatement("""
        SELECT task_id, task_name FROM daily_remaining_by_user
        WHERE user_id = %s AND date = %s
    """)
    return list(session.execute(query, (user_id, today)))

def remove_from_today(user_id: str, task_id):
    today = datetime.now(TZ).date()
    query = SimpleStatement("""
        DELETE FROM daily_remaining_by_user
        WHERE user_id = %s AND date = %s AND task_id = %s
    """)
    session.execute(query, (user_id, today, task_id))

def add_to_today(user_id: str, task_id, task_name: str):
    """Safe upsert; ok to call repeatedly."""
    now_ts = datetime.now(TZ)
    today = now_ts.date()
    query = SimpleStatement("""
        INSERT INTO daily_remaining_by_user (user_id, date, task_id, task_name, added_at)
        VALUES (%s, %s, %s, %s, %s)
        IF NOT EXISTS
    """)
    session.execute(query, (user_id, today, task_id, task_name, now_ts))

from cassandra.query import SimpleStatement

def today_dow_sunday0(now_local: datetime) -> int:
    return (now_local.weekday() + 1) % 7

def seed_today_from_reminders():
    """
    Fill daily_remaining_by_user for all users/tasks due today:
    - daily (dow = -1) across 24 hours
    - weekly for today's DOW across 24 hours
    """
    now_local = datetime.now(TZ)
    today = now_local.date()
    today_dow = today_dow_sunday0(now_local)

    query_daily = SimpleStatement("""
        SELECT user_id, task_id FROM reminders_by_time
        WHERE reminder_type = 'daily' AND reminder_hour = %s AND reminder_day_of_week = %s
    """)
    query_weekly = SimpleStatement("""
        SELECT user_id, task_id FROM reminders_by_time
        WHERE reminder_type = 'weekly' AND reminder_hour = %s AND reminder_day_of_week = %s
    """)

    per_user = {}
    for hr in range(24):
        for row in session.execute(query_daily, (hr, DAILY_SENTINEL_DOW)):
            per_user.setdefault(row.user_id, set()).add(row.task_id)
        for row in session.execute(query_weekly, (hr, today_dow)):
            per_user.setdefault(row.user_id, set()).add(row.task_id)

    ins = SimpleStatement("""
        INSERT INTO daily_remaining_by_user (user_id, date, task_id, task_name, added_at)
        VALUES (%s, %s, %s, %s, toTimestamp(now()))
        IF NOT EXISTS
    """)
    for user_id, tids in per_user.items():
        for tid in tids:
            trow = get_user_task(user_id, tid)
            name = getattr(trow, "task_name", str(tid)) if trow else str(tid)
            session.execute(ins, (user_id, today, tid, name))
