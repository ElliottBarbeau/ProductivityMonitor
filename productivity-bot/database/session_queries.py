from .cassandra_client import session

def create_sessions_table():
    query = """
                CREATE TABLE sessions_by_user_task (
                    user_id UUID,
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
