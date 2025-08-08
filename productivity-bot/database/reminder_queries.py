from .cassandra_client import session

def create_active_tasks_table():
    query = """
                CREATE TABLE reminders_by_time (
                    reminder_type TEXT,
                    reminder_hour INT,
                    reminder_minute INT,
                    reminder_day_of_week INT,
                    task_id UUID,
                    user_id UUID,
                    PRIMARY KEY ((reminder_type, reminder_hour), reminder_minute, task_id)
                );
            """

    # type = daily, weekly, monthly etc
        
    session.execute(query)

def get_daily_reminders(hour, minute_bottom, minute_top):
    query = """
                SELECT * FROM reminders_by_time
                WHERE reminder_type = 'daily' AND reminder_hour = %s and reminder_minute >= %s and reminder_minute < %s
            """
    
    result = session.execute(query, (hour, minute_bottom, minute_top))
    return list(result)


def get_daily_reminders(day, hour, minute_bottom, minute_top):
    query = """
                SELECT * FROM reminders_by_time
                WHERE reminder_type = 'weekly' AND reminder_day_of_week = day AND reminder_hour = %s and reminder_minute >= %s and reminder_minute < %s
            """
    
    result = session.execute(query, (day, hour, minute_bottom, minute_top))
    return list(result)
