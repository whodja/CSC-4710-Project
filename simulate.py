"""
simulate.py  –  Panther Cloud Air 14-day simulation runner
Run:  python simulate.py
Requires MariaDB reachable via env vars (same as app.py).
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
    Connection parameters are read from environment variables (same as db.py).
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
SIM_START      = datetime.date(2025, 3, 1)   # calendar date assigned to Day 1
FUEL_PRICE     = 6.19                         # $/gal — 2024 US average jet fuel price
LANDING_FEE    = 2000.00                      # $ per landing — flat fee charged at each destination
DAYS           = 14                           # total simulation days to run
MARKET_SHARE   = 0.02                         # PCA captures 2% of each city-pair's total demand
DAILY_FLY_RATE = 0.005                        # fraction of a metro's population that flies on any given day
MIN_CONN_MIN   = 30                           # standard minimum layover time in minutes (BFS default)
AIRPORT_CLOSE  = 1500                         # latest allowed arrival in minutes from midnight (25:00 = 1 AM next day)
FIRST_DEP      = 300                          # earliest permitted departure in minutes from midnight (05:00 AM)

# Passenger seat-class booking weights used by random.choices() in simulate_day().
# 80% economy / 15% business / 5% first class reflects typical airline booking patterns.
CLASS_SPLIT = {"economy": 0.80, "business": 0.15, "first": 0.05}

# Hub definitions
HUBS = ["ATL", "DFW", "DEN", "ORD"]

# Routes each hub serves.
# First entries are hub-to-hub connections so any OD pair
# can reach its destination in ≤3 legs: spoke→hub→hub→spoke.
# Aircraft counts: ATL=14, DFW=14, DEN=14, ORD=13
HUB_ROUTES = {
    # ATL: 3 hub-hub + 11 spokes = 14
    "ATL": ["DFW", "DEN", "ORD",
            "MCO", "MIA", "FLL", "CLT", "TPA",
            "BOS", "JFK", "EWR", "LGA", "PHL", "DTW"],
    # DFW: 2 hub-hub + 12 spokes = 14
    "DFW": ["DEN", "ORD",
            "IAH", "AUS", "PHX", "LAS", "SAN", "LAX",
            "SFO", "SLC", "MSP", "CLT", "SEA", "PDX"],
    # DEN: 1 hub-hub + 13 spokes = 14
    "DEN": ["ORD",
            "SLC", "PHX", "LAS", "LAX", "SFO", "SAN",
            "SEA", "PDX", "MSP", "IAH", "MCO", "BOS", "HNL"],
    # ORD: 13 spokes
    "ORD": ["MSP", "DTW", "BOS", "JFK", "EWR", "LGA",
            "PHL", "DCA", "BWI", "IAD", "CLT", "MIA", "SFO"],
}

# Approximate coordinates for bearing calculation
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
}

# ── Physics helpers ────────────────────────────────────────────────────────────
def bearing(orig, dest):
    """Return the initial compass bearing (0-360°) from orig to dest using great-circle math."""
    lat1, lon1 = math.radians(COORDS[orig][0]), math.radians(COORDS[orig][1])
    lat2, lon2 = math.radians(COORDS[dest][0]), math.radians(COORDS[dest][1])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    brg = math.degrees(math.atan2(x, y)) % 360
    return brg

def wind_factor(brg_deg):
    """East-bound faster (×0.955), west-bound slower (×1.045)."""
    rad = math.radians(brg_deg)
    return 1.0 - math.sin(rad) * 0.045

def jet_stream_factor(brg_deg, eastward_bonus=0.12):
    """Day-7 jet stream: east +12% speed, west -12% speed."""
    rad = math.radians(brg_deg)
    return 1.0 - math.sin(rad) * eastward_bonus

def calc_flight_time(dist_nm, cruise_kts, orig, dest, extra_factor=1.0):
    """
    Phase-by-phase flight time in minutes.
    Taxi: 10 min out + 10 min in.
    Climb: 250 kts to 10,000 ft (6° angle), then 280 kts to cruise alt.
    Cruise: distance-adjusted for wind and extra_factor.
    Descent: 1,000 ft per 3 NM → ~FL350 needs ~105 NM.
    """
    brg = bearing(orig, dest)
    wf  = wind_factor(brg) * extra_factor

    # Taxi
    taxi_min = 20

    # Ascent distance & time (simplified)
    ascent_dist_nm  = 80   # nm used during climb
    ascent_time_min = 22   # min for climb phases

    # Descent
    descent_dist_nm  = 60
    descent_time_min = 18

    # Cruise
    cruise_dist = max(dist_nm - ascent_dist_nm - descent_dist_nm, 10)
    cruise_speed = cruise_kts * wf
    cruise_min   = (cruise_dist / cruise_speed) * 60

    return taxi_min + ascent_time_min + cruise_min + descent_time_min

def calc_fuel_cost(dist_nm, cruise_kts, model_row, orig, dest, extra_factor=1.0):
    """Returns fuel cost in USD."""
    duration = calc_flight_time(dist_nm, cruise_kts, orig, dest, extra_factor)
    # Use cruise burn for bulk; simplified (burn_rate_cruise * duration)
    gal = float(model_row["burn_rate_cruise"]) * duration
    return gal * FUEL_PRICE

# ── Load reference data ────────────────────────────────────────────────────────
def load_airports(conn):
    """Return all airports as a dict keyed by IATA code."""
    return {r["iata_code"]: r for r in qall(conn, "SELECT * FROM Airports")}

def load_aircraft(conn):
    """Return all active aircraft joined with model specs, keyed by aircraft_id."""
    rows = qall(conn, """
        SELECT a.aircraft_id, a.tail_number, a.model_id, a.status,
               m.cruise_speed_kts, m.max_passengers,
               m.seat_config_economy, m.seat_config_business, m.seat_config_first,
               m.burn_rate_cruise, m.monthly_lease_usd, m.model_name,
               m.burn_rate_taxi, m.burn_rate_takeoff, m.burn_rate_ascent_low,
               m.burn_rate_ascent_high, m.burn_rate_descent_high,
               m.burn_rate_descent_low, m.burn_rate_landing
        FROM Aircraft a
        JOIN Aircraft_models m ON a.model_id = m.model_id
        WHERE a.status = 'active'
    """)
    return {r["aircraft_id"]: r for r in rows}

def load_distances(conn):
    """
    Return two dicts built from active Flight_distances rows:
      dist_map: (orig_iata, dest_iata) -> distance in nautical miles
      dist_id:  (orig_iata, dest_iata) -> Flight_distances.id (FK used when inserting flights)
    """
    rows = qall(conn, """
        SELECT fd.id, fd.distance_nm,
               o.iata_code AS orig, d.iata_code AS dest
        FROM Flight_distances fd
        JOIN Airports o ON fd.origin_id      = o.airport_id
        JOIN Airports d ON fd.destination_id = d.airport_id
        WHERE fd.is_active = TRUE
    """)
    dist_map = {}        # (orig,dest) -> distance_nm
    dist_id  = {}        # (orig,dest) -> fd.id
    for r in rows:
        key = (r["orig"], r["dest"])
        dist_map[key] = r["distance_nm"]
        dist_id[key]  = r["id"]
    return dist_map, dist_id

def load_pricing(conn):
    """
    Return a dict of seat_class -> {base, per_nm, margin} from Pricing_rules
    and the profit_margin percentage from System_config.
    """
    rules = qall(conn, "SELECT seat_class, base_price_usd, price_per_nm FROM Pricing_rules")
    cfg   = qone(conn, "SELECT config_value FROM System_config WHERE config_key='profit_margin'")
    margin = float(cfg["config_value"]) if cfg else 0.0
    pricing = {}
    for r in rules:
        pricing[r["seat_class"]] = {
            "base": float(r["base_price_usd"]),
            "per_nm": float(r["price_per_nm"]),
            "margin": margin,
        }
    return pricing

def calc_fare(seat_class, dist_nm, pricing):
    """Calculate ticket price: (base + per_nm * distance) * (1 + margin%)."""
    p = pricing[seat_class]
    return round((p["base"] + p["per_nm"] * dist_nm) * (1 + p["margin"] / 100), 2)

# ── Aircraft assignment to hubs ────────────────────────────────────────────────
def assign_hub_aircraft(aircraft):
    """
    Distribute 55 domestic aircraft (IDs 1-55) across 4 hubs.
    A350-900 (ID 56) excluded – operates international (JFK-CDG).
    ATL: IDs  1-7  + 16-22  = 14  (first 3 fly hub-hub, rest fly spokes)
    DFW: IDs  8-14 + 23-29  = 14  (first 2 fly hub-hub, rest fly spokes)
    DEN: IDs 15    + 30-42  = 14  (first 1 flies hub-hub, rest fly spokes)
    ORD: IDs 43-55           = 13  (all fly spokes; hub-hub served by other hubs)
    """
    hub_ac = {h: [] for h in HUBS}
    for aid in sorted(aircraft.keys()):
        if aid == 56:
            continue
        if 1 <= aid <= 7 or 16 <= aid <= 22:
            hub_ac["ATL"].append(aid)
        elif 8 <= aid <= 14 or 23 <= aid <= 29:
            hub_ac["DFW"].append(aid)
        elif aid == 15 or 30 <= aid <= 42:
            hub_ac["DEN"].append(aid)
        elif 43 <= aid <= 55:
            hub_ac["ORD"].append(aid)
    return hub_ac

# ── Build timetable ────────────────────────────────────────────────────────────
def generate_timetable(conn, airports, dist_map, dist_id, hub_ac, aircraft):
    """
    Each hub aircraft flies one round-trip per day.
    Depart hub → spoke at FIRST_DEP + slot*turnround_gap
    Return spoke → hub after turnaround (55 min).
    Stores into Sim_timetable, returns list of timetable dicts.
    """
    TURNAROUND = 55   # min on ground at spoke
    DEP_GAP    = 10   # min between successive hub departures

    timetable = []
    fn_counter = 1

    for hub in HUBS:
        spokes   = HUB_ROUTES[hub]
        ac_list  = hub_ac[hub]
        slot_min = FIRST_DEP

        for i, spoke in enumerate(spokes):
            if i >= len(ac_list):
                break
            ac_id = ac_list[i]
            ac    = aircraft[ac_id]

            key_out = (hub, spoke)
            key_ret = (spoke, hub)

            if key_out not in dist_map:
                slot_min += DEP_GAP
                continue

            dist   = dist_map[key_out]
            did    = dist_id[key_out]
            speed  = float(ac["cruise_speed_kts"])

            dur_out = int(calc_flight_time(dist, speed, hub, spoke))
            arr_out = slot_min + dur_out

            dep_ret = arr_out + TURNAROUND
            dur_ret = int(calc_flight_time(dist, speed, spoke, hub))
            arr_ret = dep_ret + dur_ret

            fn_out = f"PCS{fn_counter:04d}"
            fn_counter += 1
            fn_ret = f"PCS{fn_counter:04d}"
            fn_counter += 1

            did_ret = dist_id.get(key_ret, did)

            for fn, orig, dest, dep, arr, dur, d, d_id in [
                (fn_out, hub,   spoke, slot_min, arr_out, dur_out, dist, did),
                (fn_ret, spoke, hub,   dep_ret,  arr_ret, dur_ret, dist, did_ret),
            ]:
                if arr > AIRPORT_CLOSE + 120:   # skip if returns well past midnight
                    continue
                row_id = qexec(conn, """
                    INSERT INTO Sim_timetable
                        (flight_number, origin_iata, dest_iata, aircraft_id,
                         dep_time_min, arr_time_min, duration_min, distance_nm, dist_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (fn, orig, dest, ac_id, dep, arr, dur, d, d_id))
                timetable.append({
                    "timetable_id": row_id,
                    "flight_number": fn,
                    "origin":   orig,
                    "dest":     dest,
                    "aircraft_id": ac_id,
                    "dep_min":  dep,
                    "arr_min":  arr,
                    "dur_min":  dur,
                    "dist_nm":  d,
                    "dist_id":  d_id,
                })

            slot_min += DEP_GAP

    conn.commit()
    print(f"Timetable: {len(timetable)} routes built.")
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
    idx[(orig, dest)] = sorted list of instance dicts with dep_min & arr_min.
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
    Single BFS pass over the day's flight graph.

    State: (legs_used, current_airport, earliest_available_min, path_so_far)
    Visited key buckets avail_min into 90-min windows to prune redundant states
    without losing valid longer-connection paths.

    Returns a list of instance_ids (the chosen flight legs) or [] if no path found.
    """
    if origin == dest:
        return []
    queue = deque([(0, origin, pref_min, [])])
    visited = {}
    while queue:
        legs, cur, avail_min, path = queue.popleft()
        if legs >= max_legs:
            continue
        # Bucket the available time to avoid re-exploring states that are equivalent
        key = (cur, avail_min // 90)
        if key in visited and visited[key] <= legs:
            continue
        visited[key] = legs

        # Try direct flights first — return immediately if one is found
        for inst in flight_idx.get((cur, dest), []):
            if inst["dep_min"] >= avail_min and seat_avail.get(inst["instance_id"], 0) > 0:
                return path + [inst["instance_id"]]

        # Try all intermediate airports, hubs checked first for efficiency
        # (hub routes dominate the network so hub connections are found fastest)
        candidates = HUBS + [a for a in COORDS if a not in HUBS and a != origin and a != dest]
        for mid in candidates:
            if mid == cur or mid == dest:
                continue
            for inst in flight_idx.get((cur, mid), []):
                if inst["dep_min"] >= avail_min and seat_avail.get(inst["instance_id"], 0) > 0:
                    nxt = inst["arr_min"] + min_conn
                    if nxt <= AIRPORT_CLOSE:
                        queue.append((legs + 1, mid, nxt, path + [inst["instance_id"]]))
                    break  # take only the earliest viable flight per intermediate segment
    return []

def route_passenger(origin, dest, pref_min, flight_idx, seat_avail):
    """
    Route a passenger with progressive fallback:
    1. BFS with 30-min min connection (standard)
    2. BFS with 15-min min connection (tight)
    3. BFS with 0-min connection from any time (ensures path found if one exists)
    Returns list of instance_ids or [] if no path in the network.
    """
    for min_conn, start in [(MIN_CONN_MIN, pref_min), (15, pref_min), (0, FIRST_DEP)]:
        result = _bfs(origin, dest, start, flight_idx, seat_avail, min_conn, max_legs=3)
        if result:
            return result
    return []

# ── Daily challenges ──────────────────────────────────────────────────────────
# Each entry: day_number -> (description, params_dict)
# Supported param keys:
#   delay_origin  : single IATA code whose departures are delayed
#   delay_origins : list of IATA codes whose departures are delayed
#   delay_min     : minutes to add to dep_min / arr_min for affected flights
#   reason        : human-readable delay cause stored in Sim_flight_instances
#   west_factor   : multiplier applied to westbound flight durations (> 1.0 = slower)
#   jet_stream    : True triggers the day-7 bi-directional jet stream logic
#   aog_hub       : IATA code of hub whose first assigned aircraft is grounded (AOG)
#   cancel_western: True cancels all flights touching the WESTERN airport set
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
    14: ("Normal ops – final day",  {}),
}

WESTERN = {"LAX", "SFO", "SAN", "SEA", "PDX", "HNL"}

def apply_challenge(day, instances, aircraft, dist_map, hub_ac):
    """Mutate instance dicts in-place for day's challenge."""
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
            inst["dep_min"]    += delay_min
            inst["arr_min"]    += delay_min
            inst["delay_min"]  += delay_min
            inst["delay_reason"] = params.get("reason", "Delay")

        # Jet stream day 7
        if params.get("jet_stream"):
            brg = bearing(inst["origin"], inst["dest"])
            jf  = jet_stream_factor(brg)
            extra = int(inst["dur_min"] * abs(1.0 - jf))
            if jf < 1.0:   # westbound – slower
                inst["dep_min"]   += 0
                inst["arr_min"]   += extra
                inst["dur_min"]   += extra
            else:            # eastbound – faster
                inst["arr_min"]   -= extra
                inst["dur_min"]   -= extra
            inst["delay_reason"] = "Jet stream"

        # Westbound factor day 5
        if params.get("west_factor"):
            brg = bearing(inst["origin"], inst["dest"])
            if 180 < brg < 360:   # westbound
                extra = int(inst["dur_min"] * (params["west_factor"] - 1.0))
                inst["arr_min"] += extra
                inst["dur_min"] += extra
                inst["delay_min"] += extra
                inst["delay_reason"] = "Jet stream advisory"

        # Western cancellations day 10
        if params.get("cancel_western"):
            if inst["origin"] in WESTERN or inst["dest"] in WESTERN:
                inst["status"] = "cancelled"
                inst["delay_reason"] = "Western route cancellation"

    # AOG: cancel one aircraft's flights at hub
    if "aog_hub" in params:
        hub = params["aog_hub"]
        ac_ids = hub_ac.get(hub, [])
        if ac_ids:
            aog_id = ac_ids[0]   # ground first aircraft
            for inst in instances:
                if inst["aircraft_id"] == aog_id:
                    inst["status"] = "cancelled"
                    inst["delay_reason"] = "Aircraft AOG"

    return desc

# ── Simulate one day ──────────────────────────────────────────────────────────
def simulate_day(conn, day, timetable, airports, aircraft, dist_map, dist_id,
                 pricing, demand, hub_ac):
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
    desc, params = CHALLENGES[day]

    # ── Step 1: Clone timetable into mutable per-day instances ───────
    # Each instance starts as a copy of the timetable row so challenges
    # can modify departure/arrival times without altering the template.
    instances = []
    for t in timetable:
        inst = {
            "timetable_id": t["timetable_id"],
            "sim_day":     day,
            "flight_date": flight_date,
            "flight_number": f"D{day:02d}{t['flight_number']}",  # e.g. D01PCS0001
            "origin":      t["origin"],
            "dest":        t["dest"],
            "aircraft_id": t["aircraft_id"],
            "tail_number": aircraft[t["aircraft_id"]]["tail_number"],
            "dep_min":     t["dep_min"],   # minutes from midnight
            "arr_min":     t["arr_min"],
            "dur_min":     t["dur_min"],
            "dist_nm":     t["dist_nm"],
            "dist_id":     t["dist_id"],
            "status":      "scheduled",
            "delay_min":   0,
            "delay_reason": None,
            "passengers_boarded": 0,
            "gate_used":   None,
            "instance_id": None,           # assigned after INSERT below
        }
        instances.append(inst)

    # ── Step 2: Apply today's operational challenge ───────────────────
    # Mutates dep_min/arr_min/status in-place for affected flights.
    challenge_desc = apply_challenge(day, instances, aircraft, dist_map, hub_ac)

    # ── Step 3: Persist flight instances to the database ─────────────
    for inst in instances:
        base_dt   = datetime.datetime.combine(flight_date, datetime.time(0, 0))
        sched_dep = base_dt + datetime.timedelta(minutes=t["dep_min"])   # placeholder
        sched_dep = base_dt + datetime.timedelta(minutes=inst["dep_min"])
        sched_arr = base_dt + datetime.timedelta(minutes=inst["arr_min"])
        # Cancelled flights have no actual times
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
        inst["instance_id"] = iid   # store DB-assigned ID for later FK use

    # ── Step 4a: Build seat availability map ──────────────────────────
    # Maps instance_id -> remaining seats (starts at max_passengers).
    # Decremented as passengers board; BFS skips full flights.
    seat_avail = {}
    for inst in instances:
        if inst["status"] != "cancelled":
            ac = aircraft[inst["aircraft_id"]]
            seat_avail[inst["instance_id"]] = ac["max_passengers"]

    # Index flights by (origin, dest) for fast BFS lookup
    flight_idx = build_flight_index(instances)

    # ── Step 4b: Generate demand and route each passenger ─────────────
    total_pax  = 0
    arrived    = 0
    stranded   = 0
    revenue    = 0.0

    for (orig, dest), avg_n in demand.items():
        # Add ±10% Gaussian noise around the expected daily passenger count
        n = max(1, round(avg_n + random.gauss(0, avg_n * 0.1)))
        for _ in range(n):
            # Each passenger picks a random preferred departure window
            pref_min = random.randint(FIRST_DEP, AIRPORT_CLOSE - 120)
            # Seat class split mirrors CLASS_SPLIT constant (80/15/5)
            seat_class = random.choices(
                ["economy", "business", "first"],
                weights=[80, 15, 5]
            )[0]

            # BFS finds the best sequence of flight legs for this passenger
            iid_path = route_passenger(orig, dest, pref_min, flight_idx, seat_avail)

            # Sum fares across each leg of the itinerary
            total_fare = 0.0
            for iid in iid_path:
                inst_match = next(i for i in instances if i["instance_id"] == iid)
                total_fare += calc_fare(seat_class, inst_match["dist_nm"], pricing)

            status = "arrived" if iid_path else "stranded"
            total_pax += 1
            if iid_path:
                arrived += 1
                revenue += total_fare
            else:
                stranded += 1

            # Record the passenger and their fare in the DB
            pid = qexec(conn, """
                INSERT INTO Sim_passengers
                    (sim_day, origin_iata, dest_iata, preferred_dep_min,
                     status, seat_class, fare_paid)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (day, orig, dest, pref_min, status, seat_class, round(total_fare, 2)))

            # Insert one row per flight leg and decrement remaining seats
            for leg_num, iid in enumerate(iid_path, 1):
                inst_match = next(i for i in instances if i["instance_id"] == iid)
                base_dt = datetime.datetime.combine(flight_date, datetime.time(0, 0))
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

    # Push the final boarded count back to each flight instance row
    for inst in instances:
        if inst["instance_id"] and inst["passengers_boarded"] > 0:
            qexec(conn, """
                UPDATE Sim_flight_instances SET passengers_boarded=%s WHERE instance_id=%s
            """, (inst["passengers_boarded"], inst["instance_id"]))

    # ── Step 5: Compute operating costs ──────────────────────────────
    fuel_cost    = 0.0
    landing_fees = 0.0
    # Daily lease = monthly_lease / 30 days, summed across all unique aircraft used today
    lease_cost   = sum(
        float(aircraft[aid]["monthly_lease_usd"]) / 30
        for aid in set(t["aircraft_id"] for t in timetable)
    )

    for inst in instances:
        if inst["status"] == "cancelled":
            continue
        ac = aircraft[inst["aircraft_id"]]
        fuel_cost    += calc_fuel_cost(inst["dist_nm"],
                                        float(ac["cruise_speed_kts"]),
                                        ac, inst["origin"], inst["dest"])
        landing_fees += LANDING_FEE   # flat $2,000 per landing

    # Flight-level summary counters
    operated   = sum(1 for i in instances if i["status"] != "cancelled")
    cancelled  = sum(1 for i in instances if i["status"] == "cancelled")
    delayed    = sum(1 for i in instances if i["delay_min"] > 0 and i["status"] != "cancelled")
    total_delay= sum(i["delay_min"] for i in instances)

    op_cost    = fuel_cost + landing_fees + lease_cost
    profit     = revenue - op_cost

    qexec(conn, """
        INSERT INTO Sim_daily_report
            (sim_day, flight_date, total_flights_scheduled, total_flights_operated,
             total_flights_cancelled, total_flights_delayed, total_passengers,
             total_delay_min, fuel_cost_usd, landing_fees_usd, lease_cost_usd,
             revenue_usd, operating_cost_usd, profit_loss_usd, challenge_description)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (day, flight_date, len(instances), operated, cancelled, delayed,
          total_pax, total_delay, round(fuel_cost,2), round(landing_fees,2),
          round(lease_cost,2), round(revenue,2), round(op_cost,2),
          round(profit,2), challenge_desc))

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
        "dur_hrs": sum(i["dur_min"] for i in instances if i["status"]!="cancelled") / 60,
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
          round(T["dur_hrs"],2),
          round(T["fuel"],2), round(T["landing"],2), round(T["lease"],2),
          round(T["op_cost"],2), round(T["revenue"],2), round(T["profit"],2)))
    conn.commit()

    print("\n" + "="*60)
    print("  PANTHER CLOUD AIR – 14-DAY SIMULATION RESULTS")
    print("="*60)
    print(f"  Total passengers:     {T['pax']:>10,}")
    print(f"  Arrived:              {T['arrived']:>10,}")
    print(f"  Stranded:             {T['stranded']:>10,}")
    print(f"  Total flights:        {T['flights']:>10,}")
    print(f"  Operated:             {T['flights']-T['cancelled']:>10,}")
    print(f"  Cancelled:            {T['cancelled']:>10,}")
    print(f"  Delayed:              {T['delayed']:>10,}")
    print(f"  Total flight hours:   {T['dur_hrs']:>10,.1f}")
    print(f"  Fuel cost:            ${T['fuel']:>12,.2f}")
    print(f"  Landing fees:         ${T['landing']:>12,.2f}")
    print(f"  Lease cost:           ${T['lease']:>12,.2f}")
    print(f"  Operating cost:       ${T['op_cost']:>12,.2f}")
    print(f"  Revenue:              ${T['revenue']:>12,.2f}")
    print(f"  Net P&L:              ${T['profit']:>+12,.2f}")
    print("="*60)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    """
    Entry point: connect to DB, wipe previous sim tables, then run the 14-day simulation.
    Order of operations:
      1. Clear all Sim_* tables so the run is always a fresh start.
      2. Load reference data (airports, aircraft, distances, pricing).
      3. Build the repeating daily timetable once.
      4. Simulate each of 14 days using today's challenge parameters.
      5. Write the 14-day aggregate final report.
    """
    print("Panther Cloud Air – 14-day simulation starting…")
    conn = get_db()

    # Wipe all simulation tables in dependency order (children before parents)
    print("Clearing previous simulation data…")
    with conn.cursor() as c:
        for tbl in ["Sim_final_report", "Sim_daily_report", "Airport_gate_log",
                    "Sim_passenger_legs", "Sim_passengers",
                    "Sim_flight_instances", "Sim_timetable"]:
            c.execute(f"DELETE FROM {tbl}")
    conn.commit()

    # Load all reference data from the database
    airports  = load_airports(conn)
    aircraft  = load_aircraft(conn)
    dist_map, dist_id = load_distances(conn)
    pricing   = load_pricing(conn)
    # Assign each active aircraft to a hub based on aircraft_id ranges
    hub_ac    = assign_hub_aircraft(aircraft)
    # Compute expected pax/day for every origin-destination pair
    demand    = compute_demand(airports)

    print(f"Airports: {len(airports)}  |  Aircraft: {len(aircraft)}  "
          f"|  Routes in DB: {len(dist_map)}  |  OD pairs: {len(demand)}")

    # Build one repeating timetable and reuse it across all 14 days
    print("\nBuilding timetable…")
    timetable = generate_timetable(conn, airports, dist_map, dist_id, hub_ac, aircraft)

    print("\nRunning 14-day simulation…")
    daily = []
    for day in range(1, DAYS + 1):
        d = simulate_day(conn, day, timetable, airports, aircraft,
                         dist_map, dist_id, pricing, demand, hub_ac)
        daily.append(d)

    generate_final_report(conn, daily)
    conn.close()
    print("\nSimulation complete.")

if __name__ == "__main__":
    main()
