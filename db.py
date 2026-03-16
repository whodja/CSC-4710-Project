# db.py
# Handles the connection to the MariaDB database.

import mysql.connector

# Database connection settings
DB_HOST     = "localhost"
DB_PORT     = 3306
DB_NAME     = "timetable"
DB_USER     = "root"
DB_PASSWORD = "TheFutureUnemployed"


def get_connection():
    """
    Creates and returns a connection to the database.
    Call this function any time you need to run a query.
    """
    connection = mysql.connector.connect(
        host     = DB_HOST,
        port     = DB_PORT,
        database = DB_NAME,
        user     = DB_USER,
        password = DB_PASSWORD
    )
    return connection


if __name__ == "__main__":
    try:
        conn = get_connection()
        print("Connected to the database successfully!")
        conn.close()
    except:
        print("Connection failed")