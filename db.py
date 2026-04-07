# db.py
# Handles the connection to the MariaDB database.

import os
import pymysql
import pymysql.cursors

DB_HOST     = os.environ.get("DB_HOST",     "localhost")
DB_PORT     = int(os.environ.get("DB_PORT", "3306"))
DB_NAME     = os.environ.get("DB_NAME",     "timetable")
DB_USER     = os.environ.get("DB_USER",     "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "TheFutureUnemployed")


def get_connection():
    """Creates and returns a connection to the database."""
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


if __name__ == "__main__":
    try:
        conn = get_connection()
        print("Connected to the database successfully!")
        conn.close()
    except Exception as e:
        print(f"Connection failed: {e}")
