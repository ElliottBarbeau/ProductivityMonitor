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

def get_active_user_task(user_id):
    query = """
                SELECT * FROM active_tasks_by_user WHERE user_id = %s
            """
    
    result = session.execute(query, (user_id,))
    row = result.one()
    return row


def add_active_user_task(user_id, task_id, start_time):
    query = """
                INSERT INTO active_tasks_by_user (user_id, task_id, start_time)
                VALUES (%s, %s, %s);
            """
    
    session.execute(query, (user_id, task_id, start_time))

def delete_active_user_task(user_id):
    query = """
                DELETE FROM active_tasks_by_user WHERE user_id = %s
            """
    
    session.execute(query, (user_id,))
