from .cassandra_client import session

def create_active_tasks_table():
    query = """
                CREATE TABLE IF NOT EXISTS active_tasks_by_user (
                    user_id UUID,
                    task_id UUID,
                    start_time TIMESTAMP,
                    PRIMARY KEY (user_id)
                )
            """
        
    session.execute(query)

def get_active_user_task(user_id, task_id):
    query = """
                SELECT * FROM active_tasks_by_user WHERE user_id = %s AND task_id = %s
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
