from .cassandra_client import session

def create_tasks_table():
    query = """
                CREATE TABLE IF NOT EXISTS tasks_by_user (
                    user_id UUID,
                    task_id UUID,
                    task_name TEXT,
                    description TEXT,
                    reminder_type TEXT,
                    reminder_time TIME,
                    created_at TIMESTAMP,
                    PRIMARY KEY (user_id, task_id)
                )
            """
    
    # reminder_type = daily, weekly, etc
    # reminder_time = what time to ping the user at
        
    session.execute(query)

def get_user_task(user_id, task_id):
    query = """
                SELECT * FROM tasks_by_user WHERE user_id = %s AND task_id = %s
            """
    
    result = session.execute(query, (user_id, task_id))
    row = result.one()
    return row


def get_all_user_tasks(user_id):
    query = """
                SELECT * FROM tasks_by_user WHERE user_id = %s
            """
    
    result = session.execute(query, (user_id,))
    return list(result)
