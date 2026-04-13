"""

Graham McCabe
CSC-4810
app.py — Panther Cloud Air — Flask REST API
============================================
Serves the front-end static files and exposes REST endpoints that read/write
the MariaDB database managed by db.py.


ENDPOINTS
─────────
GET  /                          Serves login.html (the portal entry point)
GET  /<filename>                Serves any .html / .js / .css from the project root
GET  /api/airports              All airports ordered by metro population desc
GET  /api/aircraft              Full fleet with aircraft model specs (JOIN)
GET  /api/pricing               Cabin class pricing rules (base price + $/nm)
GET  /api/config                System configuration key→value pairs
POST /api/login                 Authenticate username + bcrypt password
POST /api/bookings              Record a passenger booking (upsert passenger row)
GET  /api/bookings/<ref>        Echo back a booking reference (decorative lookup)
"""

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.security import check_password_hash
from db import get_connection
import os
import random
import string

app = Flask(__name__)


# ── CORS helper ───────────────────────────────────────────────────────────────
@app.after_request
def add_cors_headers(response):
    """
    Attach CORS headers to every response so the front-end can reach the API
    regardless of how the HTML files are served (localhost, Docker, or file://).
    The permissive '*' origin is intentional — this is an academic project with
    no sensitive data, and restricting to a specific origin would complicate the
    demo setup.
    """
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


# ── Static front-end file serving ────────────────────────────────────────────
@app.route("/")
def index():
    """Serve the login page as the application root."""
    return send_from_directory(".", "login.html")


@app.route("/<path:filename>")
def serve_static(filename):
    """
    Serve any .html, .js, or .css file that lives in the project root directory.
    This single route covers all pages:
      login.html, airports.html, schedule.html, coverage.html,
      book.html, employee.html, admin.html,
      panther_cloud_air_shared.js, aircraft_schedule.js,
      panther_cloud_air.css, etc.

    Security note: only flat filenames (no '/' in path) with the three allowed
    extensions are served.  This prevents directory traversal attacks while
    keeping the routing dead simple.
    """
    allowed = ('.html', '.js', '.css')
    if '/' not in filename and any(filename.endswith(ext) for ext in allowed):
        return send_from_directory(".", filename)
    return "Not found", 404


# ── GET /api/airports ─────────────────────────────────────────────────────────
@app.route("/api/airports")
def api_airports():
    """
    Return the full PCA airport network ordered by metro population (highest first).

    Used by:
      - airports.html  — builds the airport network table
      - shared.js loadAirports() — populates AIRPORTS, CITY, HUBS globals in the browser
      - schedule.html, book.html, employee.html — need the city-name lookup map

    Each record contains:
      airport_id, iata_code, airport_name, city, state, timezone,
      metro_pop (integer), is_hub (0/1 → bool), gates_available

    is_hub is stored as TINYINT in MariaDB; it is converted to a Python bool
    before serialisation so the browser receives true/false rather than 0/1.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    airport_id,
                    iata_code,
                    airport_name,
                    city,
                    state,
                    timezone,
                    metro_pop,
                    is_hub,
                    gates_available
                FROM Airports
                ORDER BY metro_pop DESC
            """)
            rows = cur.fetchall()
        for r in rows:
            r["is_hub"] = bool(r["is_hub"])
        return jsonify(rows)
    finally:
        conn.close()


# ── GET /api/aircraft ─────────────────────────────────────────────────────────
@app.route("/api/aircraft")
def api_aircraft():
    """
    Return the full fleet joined with aircraft model specifications.

    Used by:
      - admin.html Fleet tab (buildFleetModelStats) — groups by model_name
        to show count, total seats, and daily lease cost per aircraft model.

    The JOIN brings together two tables:
      Aircraft       — individual tail numbers with operational status
      Aircraft_models — shared specifications per model (seats, speed, lease, etc.)

    All Decimal fields (cruise speed, range, lease cost, burn rate) are cast to
    float so Python's json.dumps can serialise them (Decimal is not JSON-serialisable).
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    a.aircraft_id,
                    a.tail_number,
                    a.status,
                    a.total_flight_hours,
                    m.model_name,
                    m.manufacturer,
                    m.max_passengers,
                    m.seat_config_economy,
                    m.seat_config_business,
                    m.seat_config_first,
                    m.cruise_speed_kts,
                    m.max_range_nm,
                    m.monthly_lease_usd,
                    m.burn_rate_cruise
                FROM Aircraft a
                JOIN Aircraft_models m ON a.model_id = m.model_id
                ORDER BY m.model_id, a.tail_number
            """)
            rows = cur.fetchall()
        for r in rows:
            for k in ("total_flight_hours", "cruise_speed_kts", "max_range_nm",
                      "monthly_lease_usd", "burn_rate_cruise"):
                if r[k] is not None:
                    r[k] = float(r[k])
        return jsonify(rows)
    finally:
        conn.close()


# ── GET /api/pricing ──────────────────────────────────────────────────────────
@app.route("/api/pricing")
def api_pricing():
    """
    Return cabin pricing rules from the Pricing_rules table.

    The table stores the DB-side fare parameters (base_price_usd + price_per_nm)
    set up by 07_pricing.sql.  In practice the browser uses getCpm() from
    localStorage for all live fare calculations, but this endpoint lets the
    admin Pricing tab confirm the DB-side rules are loaded and display the
    source of truth.

    Order: economy → business → first (using FIELD() for explicit sort).
    Fallback: if the table is empty (e.g. schema not yet seeded), returns
    hard-coded defaults so the front-end never receives an empty array.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT seat_class, base_price_usd, price_per_nm
                FROM Pricing_rules
                ORDER BY FIELD(seat_class, 'economy', 'business', 'first')
            """)
            rows = cur.fetchall()
        if not rows:
            rows = [
                {"seat_class": "economy",  "base_price_usd": 49.00,  "price_per_nm": 0.115},
                {"seat_class": "business", "base_price_usd": 107.80, "price_per_nm": 0.253},
                {"seat_class": "first",    "base_price_usd": 196.00, "price_per_nm": 0.460},
            ]
        for r in rows:
            r["base_price_usd"] = float(r["base_price_usd"])
            r["price_per_nm"]   = float(r["price_per_nm"])
        return jsonify(rows)
    finally:
        conn.close()


# ── GET /api/config ───────────────────────────────────────────────────────────
@app.route("/api/config")
def api_config():
    """
    Return all System_config rows as a flat key→value dict.

    System_config (defined in 05_fuel.sql) holds simulation-wide admin settings:
      profit_margin      — target profit margin percentage (currently informational)
      fuel_price_per_gal — jet fuel price in USD/gallon (used by simulate.py)
      taxi_time_min      — average taxi time in minutes per movement

    Example response: { "profit_margin": 0.0, "fuel_price_per_gal": 6.19 }
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT config_key, config_value FROM System_config")
            rows = cur.fetchall()
        result = {r["config_key"]: float(r["config_value"]) for r in rows}
        return jsonify(result)
    finally:
        conn.close()


# ── POST /api/login ───────────────────────────────────────────────────────────
@app.route("/api/login", methods=["POST"])
def api_login():
    """
    Authenticate a user against the Users table.

    Request body (JSON):
        { "username": "alice", "password": "secret" }

    Success response (HTTP 200):
        { "ok": true, "username": "alice", "user_type": "Admin" }

    Failure responses:
        HTTP 400  { "ok": false, "error": "Username and password required" }
        HTTP 401  { "ok": false, "error": "Invalid credentials" }

    Passwords are stored as bcrypt hashes (seeded by seed_users.py using
    werkzeug.security.generate_password_hash).  check_password_hash handles
    the bcrypt comparison securely.

    The returned user_type ("Admin" or "Employee") drives role-based navigation
    in the browser: Admin → admin.html, Employee → employee.html.
    """
    body     = request.get_json(silent=True) or {}
    username = body.get("username", "").strip()
    password = body.get("password", "").strip()

    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password required"}), 400

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, password, user_type FROM Users WHERE username = %s",
                (username,),
            )
            user = cur.fetchone()
        if user and check_password_hash(user["password"], password):
            return jsonify({"ok": True, "username": user["username"], "user_type": user["user_type"]})
        return jsonify({"ok": False, "error": "Invalid credentials"}), 401
    finally:
        conn.close()


# ── POST /api/bookings ────────────────────────────────────────────────────────
def _make_ref():
    """
    Generate a booking reference code in the format PCA-XXXXX.
    Uses 5 random uppercase letters/digits
    Example output: PCA-A3X7K
    """
    chars = string.ascii_uppercase + string.digits
    return "PCA-" + "".join(random.choices(chars, k=5))


@app.route("/api/bookings", methods=["POST"])
def api_create_booking():
    """
    Record a passenger booking in the Passengers table.

    Request body (JSON):
        {
          "first_name":      "John",
          "last_name":       "Doe",
          "email":           "john@example.com",
          "dob":             "1990-01-15",       (optional, defaults to 2000-01-01)
          "seat_class":      "economy",           (economy | business | first)
          "total_price_usd": 312.00
        }

    Success response (HTTP 200):
        { "ok": true, "booking_ref": "PCA-A3X7K" }

    Failure response (HTTP 400):
        { "ok": false, "error": "Missing field: email" }

    Implementation notes:
      - An ON DUPLICATE KEY UPDATE is used on the email column so re-booking
        with the same email address updates the passenger record rather than
        raising a duplicate-key error.
      - The flight_id FK is NOT populated because the scheduled flights live in
        the static aircraft_schedule.js array rather than the Flights DB table.
        Linking the two would require either syncing the static data to the DB
        (out of scope) or removing the FK constraint.
      - The booking_ref is generated in Python and returned to the browser for
        display on the confirmation screen.  It is not persisted to the DB in
        this version (the Passengers table does not have a booking_ref column).
    """
    body     = request.get_json(silent=True) or {}
    required = ("first_name", "last_name", "email", "seat_class", "total_price_usd")
    for field in required:
        if not body.get(field):
            return jsonify({"ok": False, "error": f"Missing field: {field}"}), 400

    dob = body.get("dob", "2000-01-01")   # date-of-birth is optional in the booking form
    ref = _make_ref()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Upsert: insert new passenger or update name/DOB if email already exists
            cur.execute("""
                INSERT INTO Passengers (first_name, last_name, email, date_of_birth)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    first_name    = VALUES(first_name),
                    last_name     = VALUES(last_name),
                    date_of_birth = VALUES(date_of_birth)
            """, (body["first_name"], body["last_name"], body["email"], dob))

        return jsonify({"ok": True, "booking_ref": ref})
    finally:
        conn.close()


@app.route("/api/bookings/<ref>")
def api_get_booking(ref):
    """
    Echo back a booking reference for the confirmation screen.

    In the current implementation the browser generates the reference itself
    (from _make_ref() via the POST response) and only needs the lookup to
    normalise the casing.  A future version would query a Bookings table here.
    """
    return jsonify({"ok": True, "booking_ref": ref.upper()})


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # debug=True enables auto-reload on code changes and the Werkzeug debugger.
    # host="0.0.0.0" makes Flask reachable from outside the container (Docker networking).
    app.run(host="0.0.0.0", port=5000, debug=True)
