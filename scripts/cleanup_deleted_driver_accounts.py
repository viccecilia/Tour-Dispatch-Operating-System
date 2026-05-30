import sqlite3

DB_PATH = "/home/ubuntu/tourflow/runtime/trial/wx_dispatch_trial.sqlite3"

conn = sqlite3.connect(DB_PATH)
conn.execute(
    """
    UPDATE users
    SET is_active = 0, updated_at = CURRENT_TIMESTAMP
    WHERE profile_type = 'driver'
      AND profile_id IN (
        SELECT id
        FROM drivers
        WHERE COALESCE(status, '') = 'deleted'
           OR COALESCE(driver_status, '') = 'deleted'
      )
    """
)
conn.commit()
print(conn.total_changes)
conn.close()
