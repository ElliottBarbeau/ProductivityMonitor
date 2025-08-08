# database/reminder_queries.py
from cassandra.query import SimpleStatement
from .cassandra_client import session

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
