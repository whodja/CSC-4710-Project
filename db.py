# db.py
# Handles the connection to the MariaDB database.
# All connection parameters are read from environment variables so that the
# same code works both locally and inside Docker (where the DB host differs).

import os
import pymysql
import pymysql.cursors

# Connection parameters — set via Docker environment or fall back to local defaults.
DB_HOST     = os.environ.get("DB_HOST",     "localhost")        # hostname / service name of the DB container
DB_PORT     = int(os.environ.get("DB_PORT", "3306"))            # MariaDB default port
DB_NAME     = os.environ.get("DB_NAME",     "timetable")        # schema name created by the init scripts
DB_USER     = os.environ.get("DB_USER",     "root")             # database user
DB_PASSWORD = os.environ.get("DB_PASSWORD", "TheFutureUnemployed")  # database password


def get_connection():
    """
    Create and return a new PyMySQL connection to the MariaDB database.

    - DictCursor: rows are returned as dicts (column name -> value) instead
      of plain tuples, making the code more readable throughout the app.
    - autocommit=True: every statement is committed immediately; no need to
      call conn.commit() after INSERT/UPDATE in app.py endpoints.
      (simulate.py opens its own connection with autocommit=False so it can
       batch-commit per simulation day.)
    """
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


# Quick connectivity smoke-test — run `python db.py` to verify the DB is reachable.
if __name__ == "__main__":
    try:
        conn = get_connection()
        print("Connected to the database successfully!")
        conn.close()
    except Exception as e:
        print(f"Connection failed: {e}")
