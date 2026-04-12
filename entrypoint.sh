#!/bin/sh
set -e

echo "[entrypoint] Waiting for MariaDB to be ready..."
python3 - <<'PYEOF'
import os, time, pymysql

for attempt in range(40):
    try:
        conn = pymysql.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", 3306)),
            database=os.environ.get("DB_NAME", "timetable"),
            user=os.environ.get("DB_USER", "root"),
            password=os.environ.get("DB_PASSWORD", "TheFutureUnemployed"),
        )
        conn.close()
        print(f"[entrypoint] Database ready after {attempt+1} attempt(s).")
        break
    except Exception as e:
        print(f"[entrypoint] DB not ready ({attempt+1}/40): {e}")
        time.sleep(3)
else:
    print("[entrypoint] ERROR: database never became ready. Exiting.")
    raise SystemExit(1)
PYEOF

echo "[entrypoint] Checking for existing simulation data..."
python3 - <<'PYEOF'
import os, sys, pymysql, pymysql.cursors, subprocess

conn = pymysql.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", 3306)),
    database=os.environ.get("DB_NAME", "timetable"),
    user=os.environ.get("DB_USER", "root"),
    password=os.environ.get("DB_PASSWORD", "TheFutureUnemployed"),
    cursorclass=pymysql.cursors.DictCursor,
)
try:
    with conn.cursor() as c:
        c.execute("SELECT COUNT(*) AS n FROM Sim_final_report")
        n = c.fetchone()["n"]
    if n == 0:
        print("[entrypoint] No simulation data found — running 14-day simulation (this may take a few minutes)...")
        result = subprocess.run(["python3", "simulate.py"], check=False)
        if result.returncode != 0:
            print("[entrypoint] WARNING: simulate.py exited with errors. App will start anyway.")
    else:
        print(f"[entrypoint] Simulation data found ({n} report). Skipping re-run.")
except Exception as e:
    print(f"[entrypoint] WARNING: could not check simulation state: {e}")
finally:
    conn.close()
PYEOF

echo "[entrypoint] Starting Flask app..."
exec python3 app.py
