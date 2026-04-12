Gracie Mitchell
CSC-4710
The Future Unemployed
File name: seed_users


"""
seed_users.py — Panther Cloud Air
===================================
Creates default system users with properly hashed passwords.
Run once at container startup (idempotent — skips if users exist).

Default credentials:
  Admin user:    username=admin    password=Admin@PCA1
  Employee user: username=employee password=Employee@PCA1

Override via environment variables:
  ADMIN_USERNAME, ADMIN_PASSWORD
  EMPLOYEE_USERNAME, EMPLOYEE_PASSWORD
"""

import os
import time
from werkzeug.security import generate_password_hash
from db import get_connection

USERS = [
    {
        "username":  os.environ.get("ADMIN_USERNAME",    "admin"),
        "password":  os.environ.get("ADMIN_PASSWORD",    "Admin@PCA1"),
        "user_type": "Admin",
    },
    {
        "username":  os.environ.get("EMPLOYEE_USERNAME", "employee"),
        "password":  os.environ.get("EMPLOYEE_PASSWORD", "Employee@PCA1"),
        "user_type": "Employee",
    },
]


def wait_for_db(retries=10, delay=3):
    """Retry loop — MariaDB may still be initialising when the web container starts."""
    for attempt in range(1, retries + 1):
        try:
            conn = get_connection()
            conn.close()
            return True
        except Exception as e:
            print(f"[seed_users] DB not ready (attempt {attempt}/{retries}): {e}")
            time.sleep(delay)
    return False


def seed():
    if not wait_for_db():
        print("[seed_users] Could not connect to DB — skipping user seed.")
        return

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for user in USERS:
                # Check if username already exists
                cur.execute("SELECT id FROM Users WHERE username = %s", (user["username"],))
                if cur.fetchone():
                    print(f"[seed_users] User '{user['username']}' already exists — skipping.")
                    continue

                hashed = generate_password_hash(user["password"], method="pbkdf2:sha256")
                cur.execute(
                    "INSERT INTO Users (username, password, user_type) VALUES (%s, %s, %s)",
                    (user["username"], hashed, user["user_type"]),
                )
                print(f"[seed_users] Created {user['user_type']} user: {user['username']}")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
