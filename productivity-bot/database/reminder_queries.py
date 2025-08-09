# database/reminder_queries.py
from cassandra.query import SimpleStatement
from .cassandra_client import session
from datetime import datetime
from collections import defaultdict

DAILY_SENTINEL_DOW = -1  # -1 for default where DOW not necessary, 0-6 otherwise

def create_reminders_table():
    query = """
        CREATE TABLE IF NOT EXISTS reminders_by_time (
            reminder_type TEXT,
            reminder_hour TINYINT,
            reminder_day_of_week TINYINT,
            reminder_minute TINYINT,
            task_id UUID,
            user_id TEXT,
            PRIMARY KEY (
                (reminder_type, reminder_hour),
                reminder_day_of_week, reminder_minute, task_id
            )
        ) WITH CLUSTERING ORDER BY (reminder_day_of_week ASC, reminder_minute ASC);
    """
    session.execute(query)

def add_reminder(reminder_type, hour, minute, user_id, task_id, day_of_week):
    dow = DAILY_SENTINEL_DOW if (day_of_week is None) else int(day_of_week)
    query = SimpleStatement("""
        INSERT INTO reminders_by_time (
            reminder_type, reminder_hour, reminder_day_of_week, reminder_minute, task_id, user_id
        ) VALUES (%s, %s, %s, %s, %s, %s)
    """)
    session.execute(query, (reminder_type, hour, minute, dow, task_id, user_id))

def delete_reminder(reminder_type, hour, minute, task_id, day_of_week):
    dow = DAILY_SENTINEL_DOW if (day_of_week is None) else int(day_of_week)
    query = SimpleStatement("""
        DELETE FROM reminders_by_time
        WHERE reminder_type = %s AND reminder_hour = %s
          AND reminder_day_of_week = %s AND reminder_minute = %s AND task_id = %s
    """)
    session.execute(query, (reminder_type, hour, minute, dow, task_id))

def get_window(reminder_type, hour, minute_bottom, minute_top, day_of_week):
    dow = DAILY_SENTINEL_DOW if (day_of_week is None) else int(day_of_week)
    query = SimpleStatement("""
        SELECT * FROM reminders_by_time
        WHERE reminder_type = %s AND reminder_hour = %s
          AND reminder_day_of_week = %s
          AND reminder_minute >= %s AND reminder_minute < %s
    """)
    return list(session.execute(query, (reminder_type, hour, dow, minute_bottom, minute_top)))

def get_daily_window(hour, minute_bottom, minute_top):
    return get_window('daily', hour, minute_bottom, minute_top, None)

def get_weekly_window(day_of_week, hour, minute_bottom, minute_top):
    return get_window('weekly', hour, minute_bottom, minute_top, day_of_week)

def fetch_due_today_user_task_ids(now_local: datetime) -> dict[str, set]:
    """
    Scan reminders_by_time for all tasks due today (daily + weekly[today]).
    Returns: { user_id (TEXT) -> set(task_id UUID) }
    """
    today_dow = today_dow_sunday0(now_local)

    by_user: dict[str, set] = defaultdict(set)

    query_daily = SimpleStatement("""
        SELECT user_id, task_id
        FROM reminders_by_time
        WHERE reminder_type = 'daily' AND reminder_hour = %s AND reminder_day_of_week = %s
    """)

    for hr in range(24):
        rows = session.execute(query_daily, (hr, DAILY_SENTINEL_DOW))
        for row in rows:
            by_user[row.user_id].add(row.task_id)

    query_weekly = SimpleStatement("""
        SELECT user_id, task_id
        FROM reminders_by_time
        WHERE reminder_type = 'weekly' AND reminder_hour = %s AND reminder_day_of_week = %s
    """)
    for hr in range(24):
        rows = session.execute(query_weekly, (hr, today_dow))
        for row in rows:
            by_user[row.user_id].add(row.task_id)

    return by_user

def today_dow_sunday0(now_local: datetime) -> int:
    return (now_local.weekday() + 1) % 7
