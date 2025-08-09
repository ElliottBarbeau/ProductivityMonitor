# database/task_queries.py
import uuid
import pytz
from datetime import time, datetime
from cassandra.query import BatchStatement, SimpleStatement
from .cassandra_client import session
from .reminder_queries import add_reminder, DAILY_SENTINEL_DOW

LOCAL_TZ = pytz.timezone("America/Toronto")

def create_tasks_table():
    query = """
        CREATE TABLE IF NOT EXISTS tasks_by_user (
            user_id TEXT,
            task_id UUID,
            task_name TEXT,
            description TEXT,
            reminder_type TEXT,
            reminder_time TIME,
            reminder_day_of_week TINYINT,
            created_at TIMESTAMP,
            PRIMARY KEY (user_id, task_id)
        )
    """
    session.execute(query)

def add_task_indexed(user_id, task_name, description, reminder_type, reminder_hour, reminder_minute, day_of_week):
    task_id = uuid.uuid4()

    # Normalize to local timezone (if user gave local time, store as that local time)
    now_local = datetime.now(LOCAL_TZ)
    rtime = time(hour=reminder_hour, minute=reminder_minute)
    dow = DAILY_SENTINEL_DOW if (day_of_week is None) else int(day_of_week)

    insert_task = SimpleStatement("""
        INSERT INTO tasks_by_user (
            user_id, task_id, task_name, description, reminder_type,
            reminder_time, reminder_day_of_week, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, toTimestamp(now()))
    """)

    insert_index = SimpleStatement("""
        INSERT INTO reminders_by_time (
            reminder_type, reminder_hour, reminder_day_of_week, reminder_minute, task_id, user_id
        ) VALUES (%s, %s, %s, %s, %s, %s)
    """)

    batch = BatchStatement()
    batch.add(insert_task, (user_id, task_id, task_name, description, reminder_type, rtime, dow))
    batch.add(insert_index, (reminder_type, reminder_hour, dow, reminder_minute, task_id, user_id))

    session.execute(batch)
    return task_id

def get_user_task(user_id, task_id):
    query = SimpleStatement("""
        SELECT * FROM tasks_by_user WHERE user_id = %s AND task_id = %s
    """)
    return session.execute(query, (user_id, task_id)).one()

def get_all_user_tasks(user_id):
    stmt = SimpleStatement("""
        SELECT * FROM tasks_by_user WHERE user_id = %s
    """)
    return list(session.execute(stmt, (user_id,)))

def delete_task_cascade(user_id, task_id, reminder_type, reminder_hour, reminder_minute, day_of_week):
    dow = DAILY_SENTINEL_DOW if (day_of_week is None) else int(day_of_week)

    del_task = SimpleStatement("""
        DELETE FROM tasks_by_user WHERE user_id = %s AND task_id = %s
    """)

    del_index = SimpleStatement("""
        DELETE FROM reminders_by_time
        WHERE reminder_type = %s AND reminder_hour = %s
        AND reminder_day_of_week = %s AND reminder_minute = %s AND task_id = %s
    """)

    batch = BatchStatement()
    batch.add(del_task, (user_id, task_id))
    batch.add(del_index, (reminder_type, reminder_hour, dow, reminder_minute, task_id))
    session.execute(batch)
