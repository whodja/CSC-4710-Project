"""
simulate.py  –  Panther Cloud Air 14-day simulation runner
Run:  python simulate.py
Requires MariaDB reachable via env vars (same as app.py).

Flight schedule is read directly from STATIC_FLIGHTS, which mirrors the
245-flight FLIGHTS array in aircraft_schedule.js so the simulation and
the browser schedule are identical.  Daily operational challenges
(delays, cancellations, jet stream, AOG) are then applied on top.
"""

import os, math, random, datetime
from collections import defaultdict, deque
import pymysql
import pymysql.cursors

# ── DB helpers ────────────────────────────────────────────────────────────────
def get_db():
    """
    Open a PyMySQL connection to MariaDB with autocommit=False.
    autocommit is disabled so each simulation day can be committed as an
    atomic unit — if anything fails mid-day the whole day can be rolled back.
    """
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", 3306)),
        database=os.environ.get("DB_NAME", "timetable"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "TheFutureUnemployed"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )

def qall(conn, sql, args=None):
    """Execute a SELECT and return all rows as a list of dicts."""
    with conn.cursor() as c:
        c.execute(sql, args or ())
        return c.fetchall()

def qone(conn, sql, args=None):
    """Execute a SELECT and return the first row, or None if empty."""
    rows = qall(conn, sql, args)
    return rows[0] if rows else None

def qexec(conn, sql, args=None):
    """Execute an INSERT/UPDATE/DELETE and return the last inserted row ID."""
    with conn.cursor() as c:
        c.execute(sql, args or ())
        return c.lastrowid

# ── Constants ─────────────────────────────────────────────────────────────────
SIM_START      = datetime.date(2025, 3, 1)
FUEL_PRICE     = 6.19          # $/gal — 2024 US average jet fuel price
LANDING_FEE    = 2000.00       # $ per landing — flat fee charged at each destination
DAYS           = 14
MARKET_SHARE   = 0.02          # PCA captures 2% of each city-pair's total demand
DAILY_FLY_RATE = 0.005         # fraction of a metro's population that flies on any given day
MIN_CONN_MIN   = 30            # standard minimum layover time in minutes
AIRPORT_CLOSE  = 1500          # latest allowed arrival in minutes from midnight (25:00)
FIRST_DEP      = 300           # earliest permitted departure in minutes from midnight (05:00)

# Passenger seat-class booking weights: 80% economy / 15% business / 5% first
CLASS_SPLIT = {"economy": 0.80, "business": 0.15, "first": 0.05}

HUBS = ["ATL", "DFW", "DEN", "ORD"]

WESTERN = {"LAX", "SFO", "SAN", "SEA", "PDX", "HNL"}

# Approximate coordinates used for bearing calculation (jet stream challenge)
COORDS = {
    "ATL": (33.64, -84.43), "DFW": (32.90, -97.04), "DEN": (39.86, -104.67),
    "ORD": (41.98, -87.91), "LAX": (33.94, -118.41), "JFK": (40.64, -73.78),
    "MCO": (28.43, -81.31), "LAS": (36.08, -115.15), "CLT": (35.21, -80.94),
    "MIA": (25.80, -80.28), "SEA": (47.45, -122.31), "EWR": (40.69, -74.17),
    "PHX": (33.44, -112.01), "IAH": (29.98, -95.34), "BOS": (42.36, -71.01),
    "FLL": (26.07, -80.15), "MSP": (44.88, -93.22), "LGA": (40.78, -73.87),
    "DTW": (42.21, -83.35), "PHL": (39.87, -75.24), "SFO": (37.62, -122.38),
    "SLC": (40.79, -111.98), "DCA": (38.85, -77.04), "BWI": (39.18, -76.67),
    "IAD": (38.94, -77.46), "TPA": (27.98, -82.53), "SAN": (32.73, -117.19),
    "PDX": (45.59, -122.60), "HNL": (21.32, -157.92), "AUS": (30.20, -97.67),
    "CDG": (49.01,   2.55),
}

# ── Static flight schedule ────────────────────────────────────────────────────
# Copied directly from aircraft_schedule.js FLIGHTS array (245 entries).
# Fields: num=flight number, tail=aircraft tail, type=model code,
#         frm/to=IATA codes, dep/arr="HH:MM" 24-hour, seats=total seat count.
STATIC_FLIGHTS = [
    {"num": "CA401", "tail": "N956CA", "type": "A359", "frm": "JFK", "to": "CDG", "dep": "05:00", "arr": "13:00", "seats": 440},
    {"num": "CA501", "tail": "N601CA", "type": "B736", "frm": "ATL", "to": "EWR", "dep": "05:00", "arr": "07:48", "seats": 110},
    {"num": "CA507", "tail": "N602CA", "type": "B736", "frm": "ATL", "to": "JFK", "dep": "05:00", "arr": "07:48", "seats": 110},
    {"num": "CA511", "tail": "N603CA", "type": "B736", "frm": "ATL", "to": "ORD", "dep": "05:00", "arr": "08:18", "seats": 110},
    {"num": "CA517", "tail": "N604CA", "type": "B736", "frm": "ATL", "to": "IAH", "dep": "05:00", "arr": "07:30", "seats": 110},
    {"num": "CA523", "tail": "N805CA", "type": "B738", "frm": "ATL", "to": "IAD", "dep": "05:00", "arr": "07:12", "seats": 162},
    {"num": "CA527", "tail": "N806CA", "type": "B738", "frm": "ATL", "to": "BOS", "dep": "05:00", "arr": "06:42", "seats": 162},
    {"num": "CA531", "tail": "N807CA", "type": "B738", "frm": "ATL", "to": "DTW", "dep": "05:00", "arr": "06:30", "seats": 162},
    {"num": "CA535", "tail": "N808CA", "type": "B738", "frm": "ATL", "to": "MSP", "dep": "05:00", "arr": "07:06", "seats": 162},
    {"num": "CA539", "tail": "N809CA", "type": "B738", "frm": "ATL", "to": "DEN", "dep": "05:00", "arr": "08:00", "seats": 162},
    {"num": "CA545", "tail": "N210CA", "type": "A221", "frm": "ATL", "to": "CLT", "dep": "05:00", "arr": "05:54", "seats": 110},
    {"num": "CA549", "tail": "N211CA", "type": "A221", "frm": "ATL", "to": "LAS", "dep": "05:00", "arr": "09:48", "seats": 110},
    {"num": "CA553", "tail": "N212CA", "type": "A221", "frm": "ATL", "to": "FLL", "dep": "05:00", "arr": "07:12", "seats": 110},
    {"num": "CA557", "tail": "N616CA", "type": "B736", "frm": "DFW", "to": "EWR", "dep": "05:00", "arr": "08:24", "seats": 110},
    {"num": "CA561", "tail": "N617CA", "type": "B736", "frm": "DFW", "to": "JFK", "dep": "05:00", "arr": "08:24", "seats": 110},
    {"num": "CA565", "tail": "N618CA", "type": "B736", "frm": "DFW", "to": "ORD", "dep": "05:00", "arr": "08:18", "seats": 110},
    {"num": "CA571", "tail": "N619CA", "type": "B736", "frm": "DFW", "to": "PHL", "dep": "05:00", "arr": "08:18", "seats": 110},
    {"num": "CA577", "tail": "N820CA", "type": "B738", "frm": "DFW", "to": "MIA", "dep": "05:00", "arr": "07:54", "seats": 162},
    {"num": "CA583", "tail": "N821CA", "type": "B738", "frm": "DFW", "to": "BOS", "dep": "05:00", "arr": "08:36", "seats": 162},
    {"num": "CA587", "tail": "N822CA", "type": "B738", "frm": "DFW", "to": "DTW", "dep": "05:00", "arr": "07:48", "seats": 162},
    {"num": "CA591", "tail": "N823CA", "type": "B738", "frm": "DFW", "to": "MSP", "dep": "05:00", "arr": "07:42", "seats": 162},
    {"num": "CA595", "tail": "N224CA", "type": "A221", "frm": "DFW", "to": "DEN", "dep": "05:00", "arr": "07:12", "seats": 110},
    {"num": "CA599", "tail": "N225CA", "type": "A221", "frm": "DFW", "to": "MCO", "dep": "05:00", "arr": "07:30", "seats": 110},
    {"num": "CA603", "tail": "N326CA", "type": "A223", "frm": "DFW", "to": "PDX", "dep": "05:00", "arr": "09:42", "seats": 132},
    {"num": "CA607", "tail": "N327CA", "type": "A223", "frm": "DFW", "to": "SLC", "dep": "05:00", "arr": "07:30", "seats": 132},
    {"num": "CA611", "tail": "N328CA", "type": "A223", "frm": "DFW", "to": "HNL", "dep": "05:00", "arr": "13:00", "seats": 132},
    {"num": "CA613", "tail": "N629CA", "type": "B736", "frm": "DEN", "to": "EWR", "dep": "05:00", "arr": "09:36", "seats": 110},
    {"num": "CA617", "tail": "N630CA", "type": "B736", "frm": "DEN", "to": "LGA", "dep": "05:00", "arr": "09:36", "seats": 110},
    {"num": "CA621", "tail": "N631CA", "type": "B736", "frm": "DEN", "to": "JFK", "dep": "05:00", "arr": "09:36", "seats": 110},
    {"num": "CA625", "tail": "N832CA", "type": "B738", "frm": "DEN", "to": "PHL", "dep": "05:00", "arr": "09:36", "seats": 162},
    {"num": "CA631", "tail": "N833CA", "type": "B738", "frm": "DEN", "to": "MIA", "dep": "05:00", "arr": "09:42", "seats": 162},
    {"num": "CA635", "tail": "N834CA", "type": "B738", "frm": "DEN", "to": "DCA", "dep": "05:00", "arr": "09:36", "seats": 162},
    {"num": "CA639", "tail": "N235CA", "type": "A221", "frm": "DEN", "to": "IAD", "dep": "05:00", "arr": "09:36", "seats": 110},
    {"num": "CA643", "tail": "N236CA", "type": "A221", "frm": "DEN", "to": "BOS", "dep": "05:00", "arr": "09:48", "seats": 110},
    {"num": "CA647", "tail": "N237CA", "type": "A221", "frm": "DEN", "to": "MCO", "dep": "05:00", "arr": "08:24", "seats": 110},
    {"num": "CA651", "tail": "N338CA", "type": "A223", "frm": "DEN", "to": "BWI", "dep": "05:00", "arr": "09:36", "seats": 132},
    {"num": "CA655", "tail": "N339CA", "type": "A223", "frm": "DEN", "to": "SAN", "dep": "05:00", "arr": "07:24", "seats": 132},
    {"num": "CA661", "tail": "N340CA", "type": "A223", "frm": "DEN", "to": "AUS", "dep": "05:00", "arr": "07:30", "seats": 132},
    {"num": "CA664", "tail": "N641CA", "type": "B736", "frm": "ORD", "to": "EWR", "dep": "05:00", "arr": "07:24", "seats": 110},
    {"num": "CA670", "tail": "N642CA", "type": "B736", "frm": "ORD", "to": "LAX", "dep": "05:00", "arr": "09:12", "seats": 110},
    {"num": "CA674", "tail": "N643CA", "type": "B736", "frm": "ORD", "to": "PHL", "dep": "05:00", "arr": "07:24", "seats": 110},
    {"num": "CA680", "tail": "N844CA", "type": "B738", "frm": "ORD", "to": "IAD", "dep": "05:00", "arr": "08:18", "seats": 162},
    {"num": "CA684", "tail": "N845CA", "type": "B738", "frm": "ORD", "to": "PHX", "dep": "05:00", "arr": "09:12", "seats": 162},
    {"num": "CA690", "tail": "N846CA", "type": "B738", "frm": "ORD", "to": "SFO", "dep": "05:00", "arr": "09:42", "seats": 162},
    {"num": "CA694", "tail": "N247CA", "type": "A221", "frm": "ORD", "to": "SEA", "dep": "05:00", "arr": "09:06", "seats": 110},
    {"num": "CA698", "tail": "N248CA", "type": "A221", "frm": "ORD", "to": "SAN", "dep": "05:00", "arr": "09:36", "seats": 110},
    {"num": "CA702", "tail": "N349CA", "type": "A223", "frm": "ORD", "to": "CLT", "dep": "05:00", "arr": "07:24", "seats": 132},
    {"num": "CA706", "tail": "N350CA", "type": "A223", "frm": "ORD", "to": "LAS", "dep": "05:00", "arr": "09:12", "seats": 132},
    {"num": "CA710", "tail": "N651CA", "type": "B736", "frm": "JFK", "to": "EWR", "dep": "05:00", "arr": "05:30", "seats": 110},
    {"num": "CA718", "tail": "N252CA", "type": "A221", "frm": "JFK", "to": "LGA", "dep": "05:00", "arr": "05:18", "seats": 110},
    {"num": "CA726", "tail": "N253CA", "type": "A221", "frm": "JFK", "to": "IAD", "dep": "05:00", "arr": "06:30", "seats": 110},
    {"num": "CA734", "tail": "N354CA", "type": "A223", "frm": "JFK", "to": "PHX", "dep": "05:00", "arr": "10:18", "seats": 132},
    {"num": "CA740", "tail": "N355CA", "type": "A223", "frm": "JFK", "to": "SFO", "dep": "05:00", "arr": "10:30", "seats": 132},
    {"num": "CA719", "tail": "N252CA", "type": "A221", "frm": "LGA", "to": "JFK", "dep": "06:03", "arr": "06:21", "seats": 110},
    {"num": "CA711", "tail": "N651CA", "type": "B736", "frm": "EWR", "to": "JFK", "dep": "06:15", "arr": "06:45", "seats": 110},
    {"num": "CA546", "tail": "N210CA", "type": "A221", "frm": "CLT", "to": "ATL", "dep": "06:39", "arr": "07:33", "seats": 110},
    {"num": "CA720", "tail": "N252CA", "type": "A221", "frm": "JFK", "to": "IAH", "dep": "07:06", "arr": "10:48", "seats": 110},
    {"num": "CA532", "tail": "N807CA", "type": "B738", "frm": "DTW", "to": "ATL", "dep": "07:15", "arr": "08:45", "seats": 162},
    {"num": "CA727", "tail": "N253CA", "type": "A221", "frm": "IAD", "to": "JFK", "dep": "07:15", "arr": "08:45", "seats": 110},
    {"num": "CA528", "tail": "N806CA", "type": "B738", "frm": "BOS", "to": "ATL", "dep": "07:27", "arr": "09:09", "seats": 162},
    {"num": "CA712", "tail": "N651CA", "type": "B736", "frm": "JFK", "to": "LGA", "dep": "07:30", "arr": "07:48", "seats": 110},
    {"num": "CA536", "tail": "N808CA", "type": "B738", "frm": "MSP", "to": "ATL", "dep": "07:51", "arr": "09:57", "seats": 162},
    {"num": "CA524", "tail": "N805CA", "type": "B738", "frm": "IAD", "to": "ATL", "dep": "07:57", "arr": "10:09", "seats": 162},
    {"num": "CA554", "tail": "N212CA", "type": "A221", "frm": "FLL", "to": "ATL", "dep": "07:57", "arr": "10:09", "seats": 110},
    {"num": "CA596", "tail": "N224CA", "type": "A221", "frm": "DEN", "to": "DFW", "dep": "07:57", "arr": "10:09", "seats": 110},
    {"num": "CA656", "tail": "N339CA", "type": "A223", "frm": "SAN", "to": "DEN", "dep": "08:09", "arr": "10:33", "seats": 132},
    {"num": "CA665", "tail": "N641CA", "type": "B736", "frm": "EWR", "to": "ORD", "dep": "08:09", "arr": "10:33", "seats": 110},
    {"num": "CA675", "tail": "N643CA", "type": "B736", "frm": "PHL", "to": "ORD", "dep": "08:09", "arr": "10:33", "seats": 110},
    {"num": "CA703", "tail": "N349CA", "type": "A223", "frm": "CLT", "to": "ORD", "dep": "08:09", "arr": "10:33", "seats": 132},
    {"num": "CA518", "tail": "N604CA", "type": "B736", "frm": "IAH", "to": "ATL", "dep": "08:15", "arr": "10:45", "seats": 110},
    {"num": "CA600", "tail": "N225CA", "type": "A221", "frm": "MCO", "to": "DFW", "dep": "08:15", "arr": "10:45", "seats": 110},
    {"num": "CA608", "tail": "N327CA", "type": "A223", "frm": "SLC", "to": "DFW", "dep": "08:15", "arr": "10:45", "seats": 132},
    {"num": "CA662", "tail": "N340CA", "type": "A223", "frm": "AUS", "to": "DEN", "dep": "08:15", "arr": "10:45", "seats": 132},
    {"num": "CA547", "tail": "N210CA", "type": "A221", "frm": "ATL", "to": "PDX", "dep": "08:18", "arr": "13:36", "seats": 110},
    {"num": "CA592", "tail": "N823CA", "type": "B738", "frm": "MSP", "to": "DFW", "dep": "08:27", "arr": "11:09", "seats": 162},
    {"num": "CA502", "tail": "N601CA", "type": "B736", "frm": "EWR", "to": "ATL", "dep": "08:33", "arr": "11:21", "seats": 110},
    {"num": "CA508", "tail": "N602CA", "type": "B736", "frm": "JFK", "to": "ATL", "dep": "08:33", "arr": "11:21", "seats": 110},
    {"num": "CA588", "tail": "N822CA", "type": "B738", "frm": "DTW", "to": "DFW", "dep": "08:33", "arr": "11:21", "seats": 162},
    {"num": "CA713", "tail": "N651CA", "type": "B736", "frm": "LGA", "to": "JFK", "dep": "08:33", "arr": "08:51", "seats": 110},
    {"num": "CA578", "tail": "N820CA", "type": "B738", "frm": "MIA", "to": "DFW", "dep": "08:39", "arr": "11:33", "seats": 162},
    {"num": "CA540", "tail": "N809CA", "type": "B738", "frm": "DEN", "to": "ATL", "dep": "08:45", "arr": "11:45", "seats": 162},
    {"num": "CA512", "tail": "N603CA", "type": "B736", "frm": "ORD", "to": "ATL", "dep": "09:03", "arr": "12:21", "seats": 110},
    {"num": "CA566", "tail": "N618CA", "type": "B736", "frm": "ORD", "to": "DFW", "dep": "09:03", "arr": "12:21", "seats": 110},
    {"num": "CA572", "tail": "N619CA", "type": "B736", "frm": "PHL", "to": "DFW", "dep": "09:03", "arr": "12:21", "seats": 110},
    {"num": "CA681", "tail": "N844CA", "type": "B738", "frm": "IAD", "to": "ORD", "dep": "09:03", "arr": "12:21", "seats": 162},
    {"num": "CA558", "tail": "N616CA", "type": "B736", "frm": "EWR", "to": "DFW", "dep": "09:09", "arr": "12:33", "seats": 110},
    {"num": "CA562", "tail": "N617CA", "type": "B736", "frm": "JFK", "to": "DFW", "dep": "09:09", "arr": "12:33", "seats": 110},
    {"num": "CA648", "tail": "N237CA", "type": "A221", "frm": "MCO", "to": "DEN", "dep": "09:09", "arr": "12:33", "seats": 110},
    {"num": "CA584", "tail": "N821CA", "type": "B738", "frm": "BOS", "to": "DFW", "dep": "09:21", "arr": "12:57", "seats": 162},
    {"num": "CA533", "tail": "N807CA", "type": "B738", "frm": "ATL", "to": "SEA", "dep": "09:30", "arr": "14:30", "seats": 162},
    {"num": "CA728", "tail": "N253CA", "type": "A221", "frm": "JFK", "to": "MIA", "dep": "09:30", "arr": "12:24", "seats": 110},
    {"num": "CA714", "tail": "N651CA", "type": "B736", "frm": "JFK", "to": "LAX", "dep": "09:36", "arr": "14:54", "seats": 110},
    {"num": "CA695", "tail": "N247CA", "type": "A221", "frm": "SEA", "to": "ORD", "dep": "09:51", "arr": "13:57", "seats": 110},
    {"num": "CA529", "tail": "N806CA", "type": "B738", "frm": "ATL", "to": "SFO", "dep": "09:54", "arr": "14:54", "seats": 162},
    {"num": "CA671", "tail": "N642CA", "type": "B736", "frm": "LAX", "to": "ORD", "dep": "09:57", "arr": "14:09", "seats": 110},
    {"num": "CA685", "tail": "N845CA", "type": "B738", "frm": "PHX", "to": "ORD", "dep": "09:57", "arr": "14:09", "seats": 162},
    {"num": "CA707", "tail": "N350CA", "type": "A223", "frm": "LAS", "to": "ORD", "dep": "09:57", "arr": "14:09", "seats": 132},
    {"num": "CA614", "tail": "N629CA", "type": "B736", "frm": "EWR", "to": "DEN", "dep": "10:21", "arr": "14:57", "seats": 110},
    {"num": "CA618", "tail": "N630CA", "type": "B736", "frm": "LGA", "to": "DEN", "dep": "10:21", "arr": "14:57", "seats": 110},
    {"num": "CA622", "tail": "N631CA", "type": "B736", "frm": "JFK", "to": "DEN", "dep": "10:21", "arr": "14:57", "seats": 110},
    {"num": "CA626", "tail": "N832CA", "type": "B738", "frm": "PHL", "to": "DEN", "dep": "10:21", "arr": "14:57", "seats": 162},
    {"num": "CA636", "tail": "N834CA", "type": "B738", "frm": "DCA", "to": "DEN", "dep": "10:21", "arr": "14:57", "seats": 162},
    {"num": "CA640", "tail": "N235CA", "type": "A221", "frm": "IAD", "to": "DEN", "dep": "10:21", "arr": "14:57", "seats": 110},
    {"num": "CA652", "tail": "N338CA", "type": "A223", "frm": "BWI", "to": "DEN", "dep": "10:21", "arr": "14:57", "seats": 132},
    {"num": "CA699", "tail": "N248CA", "type": "A221", "frm": "SAN", "to": "ORD", "dep": "10:21", "arr": "14:57", "seats": 110},
    {"num": "CA604", "tail": "N326CA", "type": "A223", "frm": "PDX", "to": "DFW", "dep": "10:27", "arr": "15:09", "seats": 132},
    {"num": "CA632", "tail": "N833CA", "type": "B738", "frm": "MIA", "to": "DEN", "dep": "10:27", "arr": "15:09", "seats": 162},
    {"num": "CA691", "tail": "N846CA", "type": "B738", "frm": "SFO", "to": "ORD", "dep": "10:27", "arr": "15:09", "seats": 162},
    {"num": "CA550", "tail": "N211CA", "type": "A221", "frm": "LAS", "to": "ATL", "dep": "10:33", "arr": "15:21", "seats": 110},
    {"num": "CA644", "tail": "N236CA", "type": "A221", "frm": "BOS", "to": "DEN", "dep": "10:33", "arr": "15:21", "seats": 110},
    {"num": "CA537", "tail": "N808CA", "type": "B738", "frm": "ATL", "to": "SAN", "dep": "10:42", "arr": "15:24", "seats": 162},
    {"num": "CA525", "tail": "N805CA", "type": "B738", "frm": "ATL", "to": "PHX", "dep": "10:54", "arr": "15:36", "seats": 162},
    {"num": "CA555", "tail": "N212CA", "type": "A221", "frm": "ATL", "to": "SLC", "dep": "10:54", "arr": "14:12", "seats": 110},
    {"num": "CA597", "tail": "N224CA", "type": "A221", "frm": "DFW", "to": "BWI", "dep": "10:54", "arr": "13:48", "seats": 110},
    {"num": "CA735", "tail": "N354CA", "type": "A223", "frm": "PHX", "to": "JFK", "dep": "11:03", "arr": "16:21", "seats": 132},
    {"num": "CA741", "tail": "N355CA", "type": "A223", "frm": "SFO", "to": "JFK", "dep": "11:15", "arr": "16:45", "seats": 132},
    {"num": "CA657", "tail": "N339CA", "type": "A223", "frm": "DEN", "to": "LAS", "dep": "11:18", "arr": "12:48", "seats": 132},
    {"num": "CA666", "tail": "N641CA", "type": "B736", "frm": "ORD", "to": "LGA", "dep": "11:18", "arr": "13:42", "seats": 110},
    {"num": "CA676", "tail": "N643CA", "type": "B736", "frm": "ORD", "to": "DCA", "dep": "11:18", "arr": "13:30", "seats": 110},
    {"num": "CA704", "tail": "N349CA", "type": "A223", "frm": "ORD", "to": "PDX", "dep": "11:18", "arr": "15:54", "seats": 132},
    {"num": "CA519", "tail": "N604CA", "type": "B736", "frm": "ATL", "to": "PHL", "dep": "11:30", "arr": "13:42", "seats": 110},
    {"num": "CA601", "tail": "N225CA", "type": "A221", "frm": "DFW", "to": "CLT", "dep": "11:30", "arr": "14:24", "seats": 110},
    {"num": "CA609", "tail": "N327CA", "type": "A223", "frm": "DFW", "to": "FLL", "dep": "11:30", "arr": "14:24", "seats": 132},
    {"num": "CA663", "tail": "N340CA", "type": "A223", "frm": "DEN", "to": "FLL", "dep": "11:30", "arr": "16:12", "seats": 132},
    {"num": "CA721", "tail": "N252CA", "type": "A221", "frm": "IAH", "to": "JFK", "dep": "11:33", "arr": "15:15", "seats": 110},
    {"num": "CA593", "tail": "N823CA", "type": "B738", "frm": "DFW", "to": "SAN", "dep": "11:54", "arr": "14:48", "seats": 162},
    {"num": "CA503", "tail": "N601CA", "type": "B736", "frm": "ATL", "to": "LGA", "dep": "12:06", "arr": "14:54", "seats": 110},
    {"num": "CA509", "tail": "N602CA", "type": "B736", "frm": "ATL", "to": "LAX", "dep": "12:06", "arr": "16:54", "seats": 110},
    {"num": "CA589", "tail": "N822CA", "type": "B738", "frm": "DFW", "to": "SEA", "dep": "12:06", "arr": "16:36", "seats": 162},
    {"num": "CA579", "tail": "N820CA", "type": "B738", "frm": "DFW", "to": "PHX", "dep": "12:18", "arr": "14:24", "seats": 162},
    {"num": "CA541", "tail": "N809CA", "type": "B738", "frm": "ATL", "to": "BWI", "dep": "12:30", "arr": "14:42", "seats": 162},
    {"num": "CA513", "tail": "N603CA", "type": "B736", "frm": "ATL", "to": "DFW", "dep": "13:06", "arr": "15:42", "seats": 110},
    {"num": "CA567", "tail": "N618CA", "type": "B736", "frm": "DFW", "to": "IAH", "dep": "13:06", "arr": "14:06", "seats": 110},
    {"num": "CA573", "tail": "N619CA", "type": "B736", "frm": "DFW", "to": "IAD", "dep": "13:06", "arr": "16:00", "seats": 110},
    {"num": "CA682", "tail": "N844CA", "type": "B738", "frm": "ORD", "to": "MIA", "dep": "13:06", "arr": "16:18", "seats": 162},
    {"num": "CA729", "tail": "N253CA", "type": "A221", "frm": "MIA", "to": "JFK", "dep": "13:09", "arr": "16:03", "seats": 110},
    {"num": "CA559", "tail": "N616CA", "type": "B736", "frm": "DFW", "to": "LGA", "dep": "13:18", "arr": "16:42", "seats": 110},
    {"num": "CA563", "tail": "N617CA", "type": "B736", "frm": "DFW", "to": "LAX", "dep": "13:18", "arr": "16:48", "seats": 110},
    {"num": "CA649", "tail": "N237CA", "type": "A221", "frm": "DEN", "to": "CLT", "dep": "13:18", "arr": "17:00", "seats": 110},
    {"num": "CA658", "tail": "N339CA", "type": "A223", "frm": "LAS", "to": "DEN", "dep": "13:33", "arr": "15:03", "seats": 132},
    {"num": "CA585", "tail": "N821CA", "type": "B738", "frm": "DFW", "to": "SFO", "dep": "13:42", "arr": "17:30", "seats": 162},
    {"num": "CA402", "tail": "N956CA", "type": "A359", "frm": "CDG", "to": "JFK", "dep": "13:45", "arr": "21:45", "seats": 440},
    {"num": "CA612", "tail": "N328CA", "type": "A223", "frm": "HNL", "to": "DFW", "dep": "13:45", "arr": "21:45", "seats": 132},
    {"num": "CA677", "tail": "N643CA", "type": "B736", "frm": "DCA", "to": "ORD", "dep": "14:15", "arr": "16:27", "seats": 110},
    {"num": "CA548", "tail": "N210CA", "type": "A221", "frm": "PDX", "to": "ATL", "dep": "14:21", "arr": "19:39", "seats": 110},
    {"num": "CA520", "tail": "N604CA", "type": "B736", "frm": "PHL", "to": "ATL", "dep": "14:27", "arr": "16:39", "seats": 110},
    {"num": "CA667", "tail": "N641CA", "type": "B736", "frm": "LGA", "to": "ORD", "dep": "14:27", "arr": "16:51", "seats": 110},
    {"num": "CA598", "tail": "N224CA", "type": "A221", "frm": "BWI", "to": "DFW", "dep": "14:33", "arr": "17:27", "seats": 110},
    {"num": "CA696", "tail": "N247CA", "type": "A221", "frm": "ORD", "to": "BWI", "dep": "14:42", "arr": "18:00", "seats": 110},
    {"num": "CA568", "tail": "N618CA", "type": "B736", "frm": "IAH", "to": "DFW", "dep": "14:51", "arr": "15:51", "seats": 110},
    {"num": "CA672", "tail": "N642CA", "type": "B736", "frm": "ORD", "to": "IAH", "dep": "14:54", "arr": "18:06", "seats": 110},
    {"num": "CA686", "tail": "N845CA", "type": "B738", "frm": "ORD", "to": "DTW", "dep": "14:54", "arr": "16:06", "seats": 162},
    {"num": "CA708", "tail": "N350CA", "type": "A223", "frm": "ORD", "to": "AUS", "dep": "14:54", "arr": "17:48", "seats": 132},
    {"num": "CA556", "tail": "N212CA", "type": "A221", "frm": "SLC", "to": "ATL", "dep": "14:57", "arr": "18:15", "seats": 110},
    {"num": "CA580", "tail": "N820CA", "type": "B738", "frm": "PHX", "to": "DFW", "dep": "15:09", "arr": "17:15", "seats": 162},
    {"num": "CA602", "tail": "N225CA", "type": "A221", "frm": "CLT", "to": "DFW", "dep": "15:09", "arr": "18:03", "seats": 110},
    {"num": "CA610", "tail": "N327CA", "type": "A223", "frm": "FLL", "to": "DFW", "dep": "15:09", "arr": "18:03", "seats": 132},
    {"num": "CA534", "tail": "N807CA", "type": "B738", "frm": "SEA", "to": "ATL", "dep": "15:15", "arr": "20:15", "seats": 162},
    {"num": "CA542", "tail": "N809CA", "type": "B738", "frm": "BWI", "to": "ATL", "dep": "15:27", "arr": "17:39", "seats": 162},
    {"num": "CA594", "tail": "N823CA", "type": "B738", "frm": "SAN", "to": "DFW", "dep": "15:33", "arr": "18:27", "seats": 162},
    {"num": "CA504", "tail": "N601CA", "type": "B736", "frm": "LGA", "to": "ATL", "dep": "15:39", "arr": "18:27", "seats": 110},
    {"num": "CA530", "tail": "N806CA", "type": "B738", "frm": "SFO", "to": "ATL", "dep": "15:39", "arr": "20:39", "seats": 162},
    {"num": "CA715", "tail": "N651CA", "type": "B736", "frm": "LAX", "to": "JFK", "dep": "15:39", "arr": "20:57", "seats": 110},
    {"num": "CA615", "tail": "N629CA", "type": "B736", "frm": "DEN", "to": "LAX", "dep": "15:42", "arr": "17:54", "seats": 110},
    {"num": "CA619", "tail": "N630CA", "type": "B736", "frm": "DEN", "to": "ORD", "dep": "15:42", "arr": "17:48", "seats": 110},
    {"num": "CA623", "tail": "N631CA", "type": "B736", "frm": "DEN", "to": "IAH", "dep": "15:42", "arr": "18:30", "seats": 110},
    {"num": "CA627", "tail": "N832CA", "type": "B738", "frm": "DEN", "to": "PHX", "dep": "15:42", "arr": "17:00", "seats": 162},
    {"num": "CA637", "tail": "N834CA", "type": "B738", "frm": "DEN", "to": "DTW", "dep": "15:42", "arr": "18:30", "seats": 162},
    {"num": "CA641", "tail": "N235CA", "type": "A221", "frm": "DEN", "to": "SEA", "dep": "15:42", "arr": "18:24", "seats": 110},
    {"num": "CA653", "tail": "N338CA", "type": "A223", "frm": "DEN", "to": "TPA", "dep": "15:42", "arr": "19:12", "seats": 132},
    {"num": "CA700", "tail": "N248CA", "type": "A221", "frm": "ORD", "to": "MCO", "dep": "15:42", "arr": "18:42", "seats": 110},
    {"num": "CA659", "tail": "N339CA", "type": "A223", "frm": "DEN", "to": "PDX", "dep": "15:48", "arr": "18:48", "seats": 132},
    {"num": "CA605", "tail": "N326CA", "type": "A223", "frm": "DFW", "to": "LAS", "dep": "15:54", "arr": "18:42", "seats": 132},
    {"num": "CA633", "tail": "N833CA", "type": "B738", "frm": "DEN", "to": "SFO", "dep": "15:54", "arr": "18:42", "seats": 162},
    {"num": "CA692", "tail": "N846CA", "type": "B738", "frm": "ORD", "to": "TPA", "dep": "15:54", "arr": "19:06", "seats": 162},
    {"num": "CA722", "tail": "N252CA", "type": "A221", "frm": "JFK", "to": "PHL", "dep": "16:00", "arr": "17:00", "seats": 110},
    {"num": "CA551", "tail": "N211CA", "type": "A221", "frm": "ATL", "to": "AUS", "dep": "16:06", "arr": "18:36", "seats": 110},
    {"num": "CA645", "tail": "N236CA", "type": "A221", "frm": "DEN", "to": "MSP", "dep": "16:06", "arr": "18:24", "seats": 110},
    {"num": "CA538", "tail": "N808CA", "type": "B738", "frm": "SAN", "to": "ATL", "dep": "16:09", "arr": "20:51", "seats": 162},
    {"num": "CA526", "tail": "N805CA", "type": "B738", "frm": "PHX", "to": "ATL", "dep": "16:21", "arr": "21:03", "seats": 162},
    {"num": "CA514", "tail": "N603CA", "type": "B736", "frm": "DFW", "to": "ATL", "dep": "16:27", "arr": "19:03", "seats": 110},
    {"num": "CA569", "tail": "N618CA", "type": "B736", "frm": "DFW", "to": "DCA", "dep": "16:36", "arr": "19:30", "seats": 110},
    {"num": "CA705", "tail": "N349CA", "type": "A223", "frm": "PDX", "to": "ORD", "dep": "16:39", "arr": "21:15", "seats": 132},
    {"num": "CA574", "tail": "N619CA", "type": "B736", "frm": "IAD", "to": "DFW", "dep": "16:45", "arr": "19:39", "seats": 110},
    {"num": "CA730", "tail": "N253CA", "type": "A221", "frm": "JFK", "to": "BOS", "dep": "16:48", "arr": "17:48", "seats": 110},
    {"num": "CA687", "tail": "N845CA", "type": "B738", "frm": "DTW", "to": "ORD", "dep": "16:51", "arr": "18:03", "seats": 162},
    {"num": "CA683", "tail": "N844CA", "type": "B738", "frm": "MIA", "to": "ORD", "dep": "17:03", "arr": "20:15", "seats": 162},
    {"num": "CA736", "tail": "N354CA", "type": "A223", "frm": "JFK", "to": "DTW", "dep": "17:06", "arr": "18:42", "seats": 132},
    {"num": "CA678", "tail": "N643CA", "type": "B736", "frm": "ORD", "to": "BOS", "dep": "17:12", "arr": "19:48", "seats": 110},
    {"num": "CA590", "tail": "N822CA", "type": "B738", "frm": "SEA", "to": "DFW", "dep": "17:21", "arr": "21:51", "seats": 162},
    {"num": "CA521", "tail": "N604CA", "type": "B736", "frm": "ATL", "to": "MIA", "dep": "17:24", "arr": "19:36", "seats": 110},
    {"num": "CA560", "tail": "N616CA", "type": "B736", "frm": "LGA", "to": "DFW", "dep": "17:27", "arr": "20:51", "seats": 110},
    {"num": "CA742", "tail": "N355CA", "type": "A223", "frm": "JFK", "to": "BWI", "dep": "17:30", "arr": "19:00", "seats": 132},
    {"num": "CA564", "tail": "N617CA", "type": "B736", "frm": "LAX", "to": "DFW", "dep": "17:33", "arr": "21:03", "seats": 110},
    {"num": "CA668", "tail": "N641CA", "type": "B736", "frm": "ORD", "to": "JFK", "dep": "17:36", "arr": "20:00", "seats": 110},
    {"num": "CA510", "tail": "N602CA", "type": "B736", "frm": "LAX", "to": "ATL", "dep": "17:39", "arr": "22:27", "seats": 110},
    {"num": "CA628", "tail": "N832CA", "type": "B738", "frm": "PHX", "to": "DEN", "dep": "17:45", "arr": "19:03", "seats": 162},
    {"num": "CA650", "tail": "N237CA", "type": "A221", "frm": "CLT", "to": "DEN", "dep": "17:45", "arr": "21:27", "seats": 110},
    {"num": "CA723", "tail": "N252CA", "type": "A221", "frm": "PHL", "to": "JFK", "dep": "17:45", "arr": "18:45", "seats": 110},
    {"num": "CA581", "tail": "N820CA", "type": "B738", "frm": "DFW", "to": "TPA", "dep": "18:00", "arr": "20:12", "seats": 162},
    {"num": "CA586", "tail": "N821CA", "type": "B738", "frm": "SFO", "to": "DFW", "dep": "18:15", "arr": "22:03", "seats": 162},
    {"num": "CA543", "tail": "N809CA", "type": "B738", "frm": "ATL", "to": "MCO", "dep": "18:24", "arr": "19:24", "seats": 162},
    {"num": "CA620", "tail": "N630CA", "type": "B736", "frm": "ORD", "to": "DEN", "dep": "18:33", "arr": "20:39", "seats": 110},
    {"num": "CA709", "tail": "N350CA", "type": "A223", "frm": "AUS", "to": "ORD", "dep": "18:33", "arr": "21:27", "seats": 132},
    {"num": "CA731", "tail": "N253CA", "type": "A221", "frm": "BOS", "to": "JFK", "dep": "18:33", "arr": "19:33", "seats": 110},
    {"num": "CA616", "tail": "N629CA", "type": "B736", "frm": "LAX", "to": "DEN", "dep": "18:39", "arr": "20:51", "seats": 110},
    {"num": "CA697", "tail": "N247CA", "type": "A221", "frm": "BWI", "to": "ORD", "dep": "18:45", "arr": "22:03", "seats": 110},
    {"num": "CA688", "tail": "N845CA", "type": "B738", "frm": "ORD", "to": "MSP", "dep": "18:48", "arr": "20:18", "seats": 162},
    {"num": "CA673", "tail": "N642CA", "type": "B736", "frm": "IAH", "to": "ORD", "dep": "18:51", "arr": "22:03", "seats": 110},
    {"num": "CA642", "tail": "N235CA", "type": "A221", "frm": "SEA", "to": "DEN", "dep": "19:09", "arr": "21:51", "seats": 110},
    {"num": "CA646", "tail": "N236CA", "type": "A221", "frm": "MSP", "to": "DEN", "dep": "19:09", "arr": "21:27", "seats": 110},
    {"num": "CA505", "tail": "N601CA", "type": "B736", "frm": "ATL", "to": "DCA", "dep": "19:12", "arr": "20:54", "seats": 110},
    {"num": "CA624", "tail": "N631CA", "type": "B736", "frm": "IAH", "to": "DEN", "dep": "19:15", "arr": "22:03", "seats": 110},
    {"num": "CA638", "tail": "N834CA", "type": "B738", "frm": "DTW", "to": "DEN", "dep": "19:15", "arr": "22:03", "seats": 162},
    {"num": "CA552", "tail": "N211CA", "type": "A221", "frm": "AUS", "to": "ATL", "dep": "19:21", "arr": "21:51", "seats": 110},
    {"num": "CA606", "tail": "N326CA", "type": "A223", "frm": "LAS", "to": "DFW", "dep": "19:27", "arr": "22:15", "seats": 132},
    {"num": "CA634", "tail": "N833CA", "type": "B738", "frm": "SFO", "to": "DEN", "dep": "19:27", "arr": "22:15", "seats": 162},
    {"num": "CA701", "tail": "N248CA", "type": "A221", "frm": "MCO", "to": "ORD", "dep": "19:27", "arr": "22:27", "seats": 110},
    {"num": "CA737", "tail": "N354CA", "type": "A223", "frm": "DTW", "to": "JFK", "dep": "19:27", "arr": "21:03", "seats": 132},
    {"num": "CA724", "tail": "N252CA", "type": "A221", "frm": "JFK", "to": "DCA", "dep": "19:30", "arr": "20:42", "seats": 110},
    {"num": "CA660", "tail": "N339CA", "type": "A223", "frm": "PDX", "to": "DEN", "dep": "19:33", "arr": "22:33", "seats": 132},
    {"num": "CA743", "tail": "N355CA", "type": "A223", "frm": "BWI", "to": "JFK", "dep": "19:45", "arr": "21:15", "seats": 132},
    {"num": "CA515", "tail": "N603CA", "type": "B736", "frm": "ATL", "to": "TPA", "dep": "19:48", "arr": "21:00", "seats": 110},
    {"num": "CA629", "tail": "N832CA", "type": "B738", "frm": "DEN", "to": "SLC", "dep": "19:48", "arr": "21:00", "seats": 162},
    {"num": "CA693", "tail": "N846CA", "type": "B738", "frm": "TPA", "to": "ORD", "dep": "19:51", "arr": "23:03", "seats": 162},
    {"num": "CA654", "tail": "N338CA", "type": "A223", "frm": "TPA", "to": "DEN", "dep": "19:57", "arr": "23:27", "seats": 132},
    {"num": "CA544", "tail": "N809CA", "type": "B738", "frm": "MCO", "to": "ATL", "dep": "20:09", "arr": "21:09", "seats": 162},
    {"num": "CA570", "tail": "N618CA", "type": "B736", "frm": "DCA", "to": "DFW", "dep": "20:15", "arr": "23:09", "seats": 110},
    {"num": "CA732", "tail": "N253CA", "type": "A221", "frm": "JFK", "to": "EWR", "dep": "20:18", "arr": "20:48", "seats": 110},
    {"num": "CA522", "tail": "N604CA", "type": "B736", "frm": "MIA", "to": "ATL", "dep": "20:21", "arr": "22:33", "seats": 110},
    {"num": "CA575", "tail": "N619CA", "type": "B736", "frm": "DFW", "to": "AUS", "dep": "20:24", "arr": "21:24", "seats": 110},
    {"num": "CA679", "tail": "N643CA", "type": "B736", "frm": "BOS", "to": "ORD", "dep": "20:33", "arr": "23:09", "seats": 110},
    {"num": "CA669", "tail": "N641CA", "type": "B736", "frm": "JFK", "to": "ORD", "dep": "20:45", "arr": "23:09", "seats": 110},
    {"num": "CA582", "tail": "N820CA", "type": "B738", "frm": "TPA", "to": "DFW", "dep": "20:57", "arr": "23:09", "seats": 162},
    {"num": "CA689", "tail": "N845CA", "type": "B738", "frm": "MSP", "to": "ORD", "dep": "21:03", "arr": "22:33", "seats": 162},
    {"num": "CA725", "tail": "N252CA", "type": "A221", "frm": "DCA", "to": "JFK", "dep": "21:27", "arr": "22:39", "seats": 110},
    {"num": "CA733", "tail": "N253CA", "type": "A221", "frm": "EWR", "to": "JFK", "dep": "21:33", "arr": "22:03", "seats": 110},
    {"num": "CA506", "tail": "N601CA", "type": "B736", "frm": "DCA", "to": "ATL", "dep": "21:39", "arr": "23:21", "seats": 110},
    {"num": "CA716", "tail": "N651CA", "type": "B736", "frm": "JFK", "to": "EWR", "dep": "21:42", "arr": "22:12", "seats": 110},
    {"num": "CA516", "tail": "N603CA", "type": "B736", "frm": "TPA", "to": "ATL", "dep": "21:45", "arr": "22:57", "seats": 110},
    {"num": "CA630", "tail": "N832CA", "type": "B738", "frm": "SLC", "to": "DEN", "dep": "21:45", "arr": "22:57", "seats": 162},
    {"num": "CA738", "tail": "N354CA", "type": "A223", "frm": "JFK", "to": "LGA", "dep": "21:48", "arr": "22:06", "seats": 132},
    {"num": "CA576", "tail": "N619CA", "type": "B736", "frm": "AUS", "to": "DFW", "dep": "22:09", "arr": "23:09", "seats": 110},
    {"num": "CA739", "tail": "N354CA", "type": "A223", "frm": "LGA", "to": "JFK", "dep": "22:51", "arr": "23:09", "seats": 132},
    {"num": "CA717", "tail": "N651CA", "type": "B736", "frm": "EWR", "to": "JFK", "dep": "22:57", "arr": "23:27", "seats": 110},
]

# ── Physics helpers ────────────────────────────────────────────────────────────
def bearing(orig, dest):
    """Return the initial compass bearing (0-360°) from orig to dest.
    Used by apply_challenge() for jet stream and westbound delay calculations."""
    lat1, lon1 = math.radians(COORDS[orig][0]), math.radians(COORDS[orig][1])
    lat2, lon2 = math.radians(COORDS[dest][0]), math.radians(COORDS[dest][1])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return math.degrees(math.atan2(x, y)) % 360

def jet_stream_factor(brg_deg, eastward_bonus=0.12):
    """Day-7 jet stream: east +12% speed (shorter duration), west -12% speed."""
    rad = math.radians(brg_deg)
    return 1.0 - math.sin(rad) * eastward_bonus

# ── Load reference data ────────────────────────────────────────────────────────
def load_airports(conn):
    """Return all airports as a dict keyed by IATA code."""
    return {r["iata_code"]: r for r in qall(conn, "SELECT * FROM Airports")}

def load_aircraft(conn):
    """
    Return all active aircraft joined with model specs, keyed by tail_number.
    Each record includes aircraft_id (DB FK), burn_rate_cruise, monthly_lease_usd,
    and max_passengers for use in cost and routing calculations.
    """
    rows = qall(conn, """
        SELECT a.aircraft_id, a.tail_number, a.model_id, a.status,
               m.cruise_speed_kts, m.max_passengers,
               m.seat_config_economy, m.seat_config_business, m.seat_config_first,
               m.burn_rate_cruise, m.monthly_lease_usd, m.model_name
        FROM Aircraft a
        JOIN Aircraft_models m ON a.model_id = m.model_id
        WHERE a.status = 'active'
    """)
    return {r["tail_number"]: r for r in rows}

def load_distances(conn):
    """
    Return two dicts from active Flight_distances rows:
      dist_map: (orig_iata, dest_iata) -> distance in nautical miles
      dist_id:  (orig_iata, dest_iata) -> Flight_distances.id (FK for Sim_timetable)
    """
    rows = qall(conn, """
        SELECT fd.id, fd.distance_nm,
               o.iata_code AS orig, d.iata_code AS dest
        FROM Flight_distances fd
        JOIN Airports o ON fd.origin_id      = o.airport_id
        JOIN Airports d ON fd.destination_id = d.airport_id
        WHERE fd.is_active = TRUE
    """)
    dist_map, dist_id = {}, {}
    for r in rows:
        key = (r["orig"], r["dest"])
        dist_map[key] = r["distance_nm"]
        dist_id[key]  = r["id"]
    return dist_map, dist_id

def load_pricing(conn):
    """Return a dict of seat_class -> {base, per_nm, margin} from Pricing_rules."""
    rules  = qall(conn, "SELECT seat_class, base_price_usd, price_per_nm FROM Pricing_rules")
    cfg    = qone(conn, "SELECT config_value FROM System_config WHERE config_key='profit_margin'")
    margin = float(cfg["config_value"]) if cfg else 0.0
    pricing = {}
    for r in rules:
        pricing[r["seat_class"]] = {
            "base":   float(r["base_price_usd"]),
            "per_nm": float(r["price_per_nm"]),
            "margin": margin,
        }
    return pricing

def calc_fare(seat_class, dist_nm, pricing):
    """Calculate ticket price: (base + per_nm * distance) * (1 + margin%)."""
    p = pricing[seat_class]
    return round((p["base"] + p["per_nm"] * dist_nm) * (1 + p["margin"] / 100), 2)

# ── Build timetable from static flights ───────────────────────────────────────
def build_timetable_from_static(conn, aircraft_by_tail, dist_map, dist_id):
    """
    Convert STATIC_FLIGHTS into Sim_timetable rows and return a list of
    timetable dicts for use as the daily template in simulate_day().

    Each STATIC_FLIGHTS entry is matched to:
      - An aircraft_id via aircraft_by_tail (tail number -> DB record)
      - A dist_nm and dist_id via dist_map / dist_id (origin, dest -> DB record)

    Flights whose tail or route are not found in the DB are skipped.
    (This silently drops the JFK-CDG international flight if CDG is not
    in the Flight_distances table, which is expected.)
    """
    def hhmm(t):
        h, m = t.split(":")
        return int(h) * 60 + int(m)

    timetable = []
    skipped   = 0

    for f in STATIC_FLIGHTS:
        # Resolve tail number to DB aircraft record
        ac = aircraft_by_tail.get(f["tail"])
        if ac is None:
            skipped += 1
            continue

        # Resolve route to distance record
        key = (f["frm"], f["to"])
        if key not in dist_map:
            skipped += 1
            continue

        dep_min = hhmm(f["dep"])
        arr_min = hhmm(f["arr"])
        if arr_min < dep_min:       # overnight arrival — add one day
            arr_min += 1440
        dur_min = arr_min - dep_min

        row_id = qexec(conn, """
            INSERT INTO Sim_timetable
                (flight_number, origin_iata, dest_iata, aircraft_id,
                 dep_time_min, arr_time_min, duration_min, distance_nm, dist_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (f["num"], f["frm"], f["to"], ac["aircraft_id"],
              dep_min, arr_min, dur_min, dist_map[key], dist_id[key]))

        timetable.append({
            "timetable_id":  row_id,
            "flight_number": f["num"],
            "origin":        f["frm"],
            "dest":          f["to"],
            "aircraft_id":   ac["aircraft_id"],
            "dep_min":       dep_min,
            "arr_min":       arr_min,
            "dur_min":       dur_min,
            "dist_nm":       dist_map[key],
            "dist_id":       dist_id[key],
            "seats":         f["seats"],
        })

    conn.commit()
    print(f"Timetable: {len(timetable)} flights loaded ({skipped} skipped — route not in DB).")
    return timetable

# ── Demand computation ────────────────────────────────────────────────────────
def compute_demand(airports):
    """
    Returns dict: (orig_iata, dest_iata) -> float passengers/day
    Formula: metro_orig * DAILY_FLY_RATE * MARKET_SHARE
             * (metro_dest / sum_of_all_other_metros)
    """
    demand = {}
    codes  = list(airports.keys())
    total_pop = sum(airports[c]["metro_pop"] for c in codes)

    for orig in codes:
        pop_o    = airports[orig]["metro_pop"]
        sum_rest = total_pop - pop_o
        daily_pax = pop_o * DAILY_FLY_RATE * MARKET_SHARE

        for dest in codes:
            if dest == orig:
                continue
            pop_d = airports[dest]["metro_pop"]
            n = daily_pax * (pop_d / sum_rest)
            if n >= 0.5:
                demand[(orig, dest)] = n

    return demand

# ── BFS passenger routing ─────────────────────────────────────────────────────
def build_flight_index(instances):
    """
    idx[(orig, dest)] = list of instance dicts sorted by dep_min.
    Cancelled flights are excluded.
    """
    idx = defaultdict(list)
    for inst in instances:
        if inst["status"] == "cancelled":
            continue
        idx[(inst["origin"], inst["dest"])].append(inst)
    for key in idx:
        idx[key].sort(key=lambda x: x["dep_min"])
    return idx

def _bfs(origin, dest, pref_min, flight_idx, seat_avail, min_conn, max_legs=3):
    """
    BFS over the day's flight graph.
    Returns a list of instance_ids (the chosen legs) or [] if no path found.
    """
    if origin == dest:
        return []
    queue   = deque([(0, origin, pref_min, [])])
    visited = {}
    while queue:
        legs, cur, avail_min, path = queue.popleft()
        if legs >= max_legs:
            continue
        key = (cur, avail_min // 90)
        if key in visited and visited[key] <= legs:
            continue
        visited[key] = legs

        for inst in flight_idx.get((cur, dest), []):
            if inst["dep_min"] >= avail_min and seat_avail.get(inst["instance_id"], 0) > 0:
                return path + [inst["instance_id"]]

        candidates = HUBS + [a for a in COORDS if a not in HUBS and a != origin and a != dest]
        for mid in candidates:
            if mid == cur or mid == dest:
                continue
            for inst in flight_idx.get((cur, mid), []):
                if inst["dep_min"] >= avail_min and seat_avail.get(inst["instance_id"], 0) > 0:
                    nxt = inst["arr_min"] + min_conn
                    if nxt <= AIRPORT_CLOSE:
                        queue.append((legs + 1, mid, nxt, path + [inst["instance_id"]]))
                    break
    return []

def route_passenger(origin, dest, pref_min, flight_idx, seat_avail):
    """
    Route a passenger with progressive fallback:
    1. BFS with 30-min min connection (standard)
    2. BFS with 15-min min connection (tight)
    3. BFS with 0-min connection from any time (last resort)
    """
    for min_conn, start in [(MIN_CONN_MIN, pref_min), (15, pref_min), (0, FIRST_DEP)]:
        result = _bfs(origin, dest, start, flight_idx, seat_avail, min_conn, max_legs=3)
        if result:
            return result
    return []

# ── Daily challenges ──────────────────────────────────────────────────────────
CHALLENGES = {
    1:  ("Normal ops", {}),
    2:  ("Winter storm at ORD – all ORD deps delayed 45 min",
         {"delay_origin": "ORD", "delay_min": 45, "reason": "Winter storm"}),
    3:  ("Icing conditions DEN – DEN deps delayed 30 min",
         {"delay_origin": "DEN", "delay_min": 30, "reason": "Icing conditions"}),
    4:  ("Gate congestion ATL – ATL deps delayed 20 min",
         {"delay_origin": "ATL", "delay_min": 20, "reason": "Gate congestion"}),
    5:  ("Jet stream advisory – westbound flights +8% time",
         {"west_factor": 1.08}),
    6:  ("High winds SEA – SEA deps delayed 35 min",
         {"delay_origin": "SEA", "delay_min": 35, "reason": "High winds"}),
    7:  ("Jet stream peak – eastbound -12%, westbound +12%",
         {"jet_stream": True}),
    8:  ("Aircraft AOG – one DFW aircraft grounded",
         {"aog_hub": "DFW"}),
    9:  ("Heavy rain MIA & FLL – deps delayed 25 min",
         {"delay_origins": ["MIA", "FLL"], "delay_min": 25, "reason": "Heavy rain"}),
    10: ("Western cancellations – all flights orig/dest LAX/SFO/SAN/SEA/PDX cancelled",
         {"cancel_western": True}),
    11: ("Fog at JFK/EWR/LGA – deps delayed 40 min",
         {"delay_origins": ["JFK", "EWR", "LGA"], "delay_min": 40, "reason": "Fog"}),
    12: ("De-icing ops DEN+ORD – deps delayed 30 min",
         {"delay_origins": ["DEN", "ORD"], "delay_min": 30, "reason": "De-icing"}),
    13: ("Staff shortage DCA/BWI/IAD – deps delayed 20 min",
         {"delay_origins": ["DCA", "BWI", "IAD"], "delay_min": 20, "reason": "Staff shortage"}),
    14: ("Normal ops – final day", {}),
}

def apply_challenge(day, instances):
    """
    Mutate instance dicts in-place for the day's operational challenge.
    For the AOG challenge the first aircraft found departing from the
    affected hub is grounded (all its flights for the day cancelled).
    """
    desc, params = CHALLENGES[day]

    delay_origins = []
    if "delay_origin" in params:
        delay_origins = [params["delay_origin"]]
    if "delay_origins" in params:
        delay_origins = params["delay_origins"]
    delay_min = params.get("delay_min", 0)

    for inst in instances:
        # Airport-specific delays
        if delay_origins and inst["origin"] in delay_origins:
            inst["dep_min"]      += delay_min
            inst["arr_min"]      += delay_min
            inst["delay_min"]    += delay_min
            inst["delay_reason"]  = params.get("reason", "Delay")

        # Jet stream (day 7) — east faster, west slower
        if params.get("jet_stream"):
            if inst["origin"] in COORDS and inst["dest"] in COORDS:
                brg   = bearing(inst["origin"], inst["dest"])
                jf    = jet_stream_factor(brg)
                extra = int(inst["dur_min"] * abs(1.0 - jf))
                if jf < 1.0:     # westbound — slower
                    inst["arr_min"] += extra
                    inst["dur_min"] += extra
                else:             # eastbound — faster
                    inst["arr_min"] -= extra
                    inst["dur_min"] -= extra
                inst["delay_reason"] = "Jet stream"

        # Westbound advisory (day 5)
        if params.get("west_factor"):
            if inst["origin"] in COORDS and inst["dest"] in COORDS:
                brg = bearing(inst["origin"], inst["dest"])
                if 180 < brg < 360:
                    extra = int(inst["dur_min"] * (params["west_factor"] - 1.0))
                    inst["arr_min"]    += extra
                    inst["dur_min"]    += extra
                    inst["delay_min"]  += extra
                    inst["delay_reason"] = "Jet stream advisory"

        # Western route cancellations (day 10)
        if params.get("cancel_western"):
            if inst["origin"] in WESTERN or inst["dest"] in WESTERN:
                inst["status"]       = "cancelled"
                inst["delay_reason"] = "Western route cancellation"

    # AOG: find first aircraft departing from the affected hub and ground it
    if "aog_hub" in params:
        hub    = params["aog_hub"]
        aog_id = None
        for inst in instances:
            if inst["origin"] == hub:
                aog_id = inst["aircraft_id"]
                break
        if aog_id:
            for inst in instances:
                if inst["aircraft_id"] == aog_id:
                    inst["status"]       = "cancelled"
                    inst["delay_reason"] = "Aircraft AOG"

    return desc

# ── Simulate one day ──────────────────────────────────────────────────────────
def simulate_day(conn, day, timetable, airports, aircraft, pricing, demand):
    """
    Simulate a single day of Panther Cloud Air operations.

    Steps:
      1. Clone the fixed timetable into a mutable list of flight instances.
      2. Apply the day's operational challenge (delays, cancellations, AOG).
      3. Insert flight instances into Sim_flight_instances.
      4. Route each demand passenger via BFS, recording legs and revenue.
      5. Compute operating costs (fuel, landing fees, lease).
      6. Write a daily summary row to Sim_daily_report.
    """
    flight_date = SIM_START + datetime.timedelta(days=day - 1)

    # ── Step 1: Clone timetable into mutable per-day instances ───────────────
    instances = []
    for t in timetable:
        instances.append({
            "timetable_id":       t["timetable_id"],
            "sim_day":            day,
            "flight_date":        flight_date,
            "flight_number":      f"D{day:02d}{t['flight_number']}",
            "origin":             t["origin"],
            "dest":               t["dest"],
            "aircraft_id":        t["aircraft_id"],
            "tail_number":        aircraft[t["aircraft_id"]]["tail_number"],
            "dep_min":            t["dep_min"],
            "arr_min":            t["arr_min"],
            "dur_min":            t["dur_min"],
            "dist_nm":            t["dist_nm"],
            "dist_id":            t["dist_id"],
            "seats":              t["seats"],
            "status":             "scheduled",
            "delay_min":          0,
            "delay_reason":       None,
            "passengers_boarded": 0,
            "instance_id":        None,
        })

    # ── Step 2: Apply today's operational challenge ───────────────────────────
    challenge_desc = apply_challenge(day, instances)

    # ── Step 3: Persist flight instances to the database ─────────────────────
    for inst in instances:
        base_dt   = datetime.datetime.combine(flight_date, datetime.time(0, 0))
        sched_dep = base_dt + datetime.timedelta(minutes=inst["dep_min"])
        sched_arr = base_dt + datetime.timedelta(minutes=inst["arr_min"])
        actual_dep = sched_dep if inst["status"] != "cancelled" else None
        actual_arr = sched_arr if inst["status"] != "cancelled" else None

        iid = qexec(conn, """
            INSERT INTO Sim_flight_instances
                (timetable_id, sim_day, flight_date, flight_number,
                 origin_iata, dest_iata, aircraft_id, tail_number,
                 scheduled_dep, scheduled_arr, actual_dep, actual_arr,
                 status, delay_reason, delay_min, distance_nm)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (inst["timetable_id"], day, flight_date, inst["flight_number"],
              inst["origin"], inst["dest"], inst["aircraft_id"], inst["tail_number"],
              sched_dep, sched_arr, actual_dep, actual_arr,
              inst["status"], inst["delay_reason"], inst["delay_min"], inst["dist_nm"]))
        inst["instance_id"] = iid

    # ── Step 4a: Seat availability and flight index ───────────────────────────
    seat_avail = {
        inst["instance_id"]: inst["seats"]
        for inst in instances
        if inst["status"] != "cancelled"
    }
    flight_idx = build_flight_index(instances)

    # ── Step 4b: Generate demand and route each passenger ─────────────────────
    total_pax = arrived = stranded = 0
    revenue   = 0.0

    for (orig, dest), avg_n in demand.items():
        n = max(1, round(avg_n + random.gauss(0, avg_n * 0.1)))
        for _ in range(n):
            pref_min   = random.randint(FIRST_DEP, AIRPORT_CLOSE - 120)
            seat_class = random.choices(
                ["economy", "business", "first"], weights=[80, 15, 5]
            )[0]

            iid_path   = route_passenger(orig, dest, pref_min, flight_idx, seat_avail)
            total_fare = sum(
                calc_fare(seat_class, next(i for i in instances if i["instance_id"] == iid)["dist_nm"], pricing)
                for iid in iid_path
            )

            total_pax += 1
            if iid_path:
                arrived  += 1
                revenue  += total_fare
            else:
                stranded += 1

            status = "arrived" if iid_path else "stranded"
            pid = qexec(conn, """
                INSERT INTO Sim_passengers
                    (sim_day, origin_iata, dest_iata, preferred_dep_min,
                     status, seat_class, fare_paid)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (day, orig, dest, pref_min, status, seat_class, round(total_fare, 2)))

            for leg_num, iid in enumerate(iid_path, 1):
                inst_match = next(i for i in instances if i["instance_id"] == iid)
                base_dt    = datetime.datetime.combine(flight_date, datetime.time(0, 0))
                sdep = base_dt + datetime.timedelta(minutes=inst_match["dep_min"])
                sarr = base_dt + datetime.timedelta(minutes=inst_match["arr_min"])
                qexec(conn, """
                    INSERT INTO Sim_passenger_legs
                        (sim_passenger_id, leg_number, instance_id,
                         scheduled_dep, actual_dep, scheduled_arr, actual_arr, status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,'booked')
                """, (pid, leg_num, iid, sdep, sdep, sarr, sarr))
                seat_avail[iid] = max(0, seat_avail[iid] - 1)
                inst_match["passengers_boarded"] += 1

    for inst in instances:
        if inst["instance_id"] and inst["passengers_boarded"] > 0:
            qexec(conn, """
                UPDATE Sim_flight_instances SET passengers_boarded=%s WHERE instance_id=%s
            """, (inst["passengers_boarded"], inst["instance_id"]))

    # ── Step 5: Compute operating costs ──────────────────────────────────────
    fuel_cost    = 0.0
    landing_fees = 0.0
    lease_cost   = sum(
        float(aircraft[aid]["monthly_lease_usd"]) / 30
        for aid in set(t["aircraft_id"] for t in timetable)
    )

    for inst in instances:
        if inst["status"] == "cancelled":
            continue
        ac = aircraft[inst["aircraft_id"]]
        # Fuel: burn rate (gal/min at cruise) × actual duration × price per gallon
        fuel_cost    += float(ac["burn_rate_cruise"]) * inst["dur_min"] * FUEL_PRICE
        landing_fees += LANDING_FEE

    operated    = sum(1 for i in instances if i["status"] != "cancelled")
    cancelled   = sum(1 for i in instances if i["status"] == "cancelled")
    delayed     = sum(1 for i in instances if i["delay_min"] > 0 and i["status"] != "cancelled")
    total_delay = sum(i["delay_min"] for i in instances)
    op_cost     = fuel_cost + landing_fees + lease_cost
    profit      = revenue - op_cost

    qexec(conn, """
        INSERT INTO Sim_daily_report
            (sim_day, flight_date, total_flights_scheduled, total_flights_operated,
             total_flights_cancelled, total_flights_delayed, total_passengers,
             total_delay_min, fuel_cost_usd, landing_fees_usd, lease_cost_usd,
             revenue_usd, operating_cost_usd, profit_loss_usd, challenge_description)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (day, flight_date, len(instances), operated, cancelled, delayed,
          total_pax, total_delay, round(fuel_cost, 2), round(landing_fees, 2),
          round(lease_cost, 2), round(revenue, 2), round(op_cost, 2),
          round(profit, 2), challenge_desc))

    conn.commit()
    print(f"  Day {day:2d} [{flight_date}] | {challenge_desc[:50]}")
    print(f"         Flights: {operated} op / {cancelled} canc / {delayed} delayed")
    print(f"         Pax: {total_pax} total, {arrived} arrived, {stranded} stranded")
    print(f"         Rev: ${revenue:,.0f}  OpCost: ${op_cost:,.0f}  P&L: ${profit:+,.0f}")

    return {
        "fuel": fuel_cost, "landing": landing_fees, "lease": lease_cost,
        "revenue": revenue, "op_cost": op_cost, "profit": profit,
        "pax": total_pax, "arrived": arrived, "stranded": stranded,
        "flights": len(instances), "operated": operated,
        "cancelled": cancelled, "delayed": delayed, "delay_min": total_delay,
        "dur_hrs": sum(i["dur_min"] for i in instances if i["status"] != "cancelled") / 60,
    }

# ── Final report ──────────────────────────────────────────────────────────────
def generate_final_report(conn, daily_totals):
    """Aggregate 14 daily result dicts and write a single summary to Sim_final_report."""
    T = {k: sum(d[k] for d in daily_totals) for k in daily_totals[0]}
    qexec(conn, """
        INSERT INTO Sim_final_report
            (total_passengers, passengers_arrived, passengers_stranded,
             total_flights, flights_cancelled, flights_delayed,
             total_flight_hours, total_fuel_cost_usd, total_landing_fees_usd,
             total_lease_cost_usd, total_operating_cost, total_revenue_usd,
             total_profit_loss_usd)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (T["pax"], T["arrived"], T["stranded"],
          T["flights"], T["cancelled"], T["delayed"],
          round(T["dur_hrs"], 2),
          round(T["fuel"], 2), round(T["landing"], 2), round(T["lease"], 2),
          round(T["op_cost"], 2), round(T["revenue"], 2), round(T["profit"], 2)))
    conn.commit()

    print("\n" + "=" * 60)
    print("  PANTHER CLOUD AIR – 14-DAY SIMULATION RESULTS")
    print("=" * 60)
    print(f"  Total passengers:     {T['pax']:>10,}")
    print(f"  Arrived:              {T['arrived']:>10,}")
    print(f"  Stranded:             {T['stranded']:>10,}")
    print(f"  Total flights:        {T['flights']:>10,}")
    print(f"  Operated:             {T['flights'] - T['cancelled']:>10,}")
    print(f"  Cancelled:            {T['cancelled']:>10,}")
    print(f"  Delayed:              {T['delayed']:>10,}")
    print(f"  Total flight hours:   {T['dur_hrs']:>10,.1f}")
    print(f"  Fuel cost:            ${T['fuel']:>12,.2f}")
    print(f"  Landing fees:         ${T['landing']:>12,.2f}")
    print(f"  Lease cost:           ${T['lease']:>12,.2f}")
    print(f"  Operating cost:       ${T['op_cost']:>12,.2f}")
    print(f"  Revenue:              ${T['revenue']:>12,.2f}")
    print(f"  Net P&L:              ${T['profit']:>+12,.2f}")
    print("=" * 60)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    """
    Entry point: connect to DB, wipe previous sim tables, then run the 14-day simulation.

    Order of operations:
      1. Clear all Sim_* tables so the run is always a fresh start.
      2. Load reference data (airports, aircraft, distances, pricing).
      3. Build the timetable once from STATIC_FLIGHTS (same flights as the browser schedule).
      4. Simulate each of 14 days, applying that day's challenge to the timetable.
      5. Write the 14-day aggregate final report.
    """
    print("Panther Cloud Air – 14-day simulation starting…")
    conn = get_db()

    print("Clearing previous simulation data…")
    with conn.cursor() as c:
        for tbl in ["Sim_final_report", "Sim_daily_report", "Airport_gate_log",
                    "Sim_passenger_legs", "Sim_passengers",
                    "Sim_flight_instances", "Sim_timetable"]:
            c.execute(f"DELETE FROM {tbl}")
    conn.commit()

    # Load reference data
    airports        = load_airports(conn)
    aircraft_by_tail = load_aircraft(conn)
    # Build an aircraft_id-keyed dict for simulate_day() lookups
    aircraft_by_id  = {r["aircraft_id"]: r for r in aircraft_by_tail.values()}
    dist_map, dist_id = load_distances(conn)
    pricing         = load_pricing(conn)
    demand          = compute_demand(airports)

    print(f"Airports: {len(airports)}  |  Aircraft: {len(aircraft_by_tail)}  "
          f"|  Routes in DB: {len(dist_map)}  |  OD pairs: {len(demand)}")

    # Build timetable from the static schedule (mirrors aircraft_schedule.js)
    print("\nLoading timetable from static schedule…")
    timetable = build_timetable_from_static(conn, aircraft_by_tail, dist_map, dist_id)

    print("\nRunning 14-day simulation…")
    daily = []
    for day in range(1, DAYS + 1):
        d = simulate_day(conn, day, timetable, airports, aircraft_by_id, pricing, demand)
        daily.append(d)

    generate_final_report(conn, daily)
    conn.close()
    print("\nSimulation complete.")

if __name__ == "__main__":
    main()
