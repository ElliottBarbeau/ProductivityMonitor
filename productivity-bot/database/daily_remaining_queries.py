# database/daily_remaining_queries.py
from datetime import datetime
from zoneinfo import ZoneInfo
from cassandra.query import SimpleStatement
from .cassandra_client import session
from .task_queries import get_user_task
from .reminder_queries import DAILY_SENTINEL_DOW

TZ = ZoneInfo("America/Toronto")

def _today_est_date():
    return datetime.now(TZ).date()

def create_daily_remaining_table():
    session.execute("""
        CREATE TABLE IF NOT EXISTS daily_remaining_by_user (
            user_id TEXT,
            date DATE,
            task_name TEXT,
            added_at TIMESTAMP,
            PRIMARY KEY ((user_id, date), task_name)
        ) WITH CLUSTERING ORDER BY (task_name ASC)
    """)

def list_remaining_today(user_id: str):
    today = _today_est_date()
    stmt = SimpleStatement("""
        SELECT task_name FROM daily_remaining_by_user
        WHERE user_id = %s AND date = %s
    """)
    return list(session.execute(stmt, (user_id, today)))

def remove_from_today(user_id: str, task_name: str):
    today = _today_est_date()
    stmt = SimpleStatement("""
        DELETE FROM daily_remaining_by_user
        WHERE user_id = %s AND date = %s AND task_name = %s
    """)
    session.execute(stmt, (user_id, today, task_name))

def add_to_today(user_id: str, task_name: str):
    """Idempotent add for today's list."""
    now_ts = datetime.now(TZ)
    today = now_ts.date()
    stmt = SimpleStatement("""
        INSERT INTO daily_remaining_by_user (user_id, date, task_name, added_at)
        VALUES (%s, %s, %s, %s) IF NOT EXISTS
    """)
    session.execute(stmt, (user_id, today, task_name, now_ts))

def today_dow_sunday0(now_local: datetime) -> int:
    # Python Mon=0..Sun=6 -> Sun=0..Sat=6
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

    q_daily = SimpleStatement("""
        SELECT user_id, task_id FROM reminders_by_time
        WHERE reminder_type = 'daily' AND reminder_hour = %s AND reminder_day_of_week = %s
    """)
    q_weekly = SimpleStatement("""
        SELECT user_id, task_id FROM reminders_by_time
        WHERE reminder_type = 'weekly' AND reminder_hour = %s AND reminder_day_of_week = %s
    """)

    per_user_names: dict[str, set[str]] = {}

    for hr in range(24):
        for row in session.execute(q_daily, (hr, DAILY_SENTINEL_DOW)):
            trow = get_user_task(row.user_id, row.task_id)
            name = getattr(trow, "task_name", None)
            if name:
                per_user_names.setdefault(row.user_id, set()).add(name)
        for row in session.execute(q_weekly, (hr, today_dow)):
            trow = get_user_task(row.user_id, row.task_id)
            name = getattr(trow, "task_name", None)
            if name:
                per_user_names.setdefault(row.user_id, set()).add(name)

    ins = SimpleStatement("""
        INSERT INTO daily_remaining_by_user (user_id, date, task_name, added_at)
        VALUES (%s, %s, %s, toTimestamp(now())) IF NOT EXISTS
    """)
    for user_id, names in per_user_names.items():
        for name in names:
            session.execute(ins, (user_id, today, name))
