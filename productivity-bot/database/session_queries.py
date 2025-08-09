from .cassandra_client import session
from cassandra.query import SimpleStatement

def create_sessions_table():
    query = """
                CREATE TABLE sessions_by_user_task (
                    user_id TEXT,
                    task_id UUID,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    duration_hours DOUBLE,
                    PRIMARY KEY ((user_id, task_id), start_time)
                ) WITH CLUSTERING ORDER BY (start_time DESC)
            """
        
    session.execute(query)

def get_all_sessions_for_task(task_id):
    query = """
                SELECT * FROM sessions_by_user_task WHERE task_id = %s
            """
    
    result = session.execute(query, (task_id,))
    return list(result)

def add_session_for_task(user_id, task_id, start_time, end_time, duration_hours):
    query = """
                INSERT INTO sessions_by_user_task (user_id, task_id, start_time, end_time, duration_hours)
                VALUES (%s, %s, %s, %s, %s)
            """
    
    session.execute(query, (user_id, task_id, start_time, end_time, duration_hours))

def get_sessions_for_user_task_range(user_id, task_id, start_from=None, end_before=None):
    """
    Returns rows for (user_id, task_id) where start_time is in [start_from, end_before).
    Pass None to skip that bound.
    """
    if start_from and end_before:
        stmt = SimpleStatement("""
            SELECT start_time, end_time, duration_hours
            FROM sessions_by_user_task
            WHERE user_id = %s AND task_id = %s
              AND start_time >= %s AND start_time < %s
        """)
        params = (user_id, task_id, start_from, end_before)
    elif start_from:
        stmt = SimpleStatement("""
            SELECT start_time, end_time, duration_hours
            FROM sessions_by_user_task
            WHERE user_id = %s AND task_id = %s
              AND start_time >= %s
        """)
        params = (user_id, task_id, start_from)
    elif end_before:
        stmt = SimpleStatement("""
            SELECT start_time, end_time, duration_hours
            FROM sessions_by_user_task
            WHERE user_id = %s AND task_id = %s
              AND start_time < %s
        """)
        params = (user_id, task_id, end_before)
    else:
        stmt = SimpleStatement("""
            SELECT start_time, end_time, duration_hours
            FROM sessions_by_user_task
            WHERE user_id = %s AND task_id = %s
        """)
        params = (user_id, task_id)

    return list(session.execute(stmt, params))
