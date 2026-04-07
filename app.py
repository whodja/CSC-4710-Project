"""
app.py  —  Panther Cloud Air  —  Flask API
===========================================
Serves the front-end and exposes REST endpoints
that read/write the MariaDB database.

Endpoints
---------
GET  /                          serve HTML front-end
GET  /api/airports              all airports (sorted by metro_pop desc)
GET  /api/aircraft              fleet list (aircraft + model specs)
GET  /api/pricing               cabin pricing rules + fuel price
GET  /api/config                system config key-value pairs
POST /api/login                 authenticate a user
POST /api/bookings              create a booking
GET  /api/bookings/<ref>        look up a booking by reference code
"""

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.security import check_password_hash
from db import get_connection
import os
import random
import string

app = Flask(__name__)


# ── CORS helper ─────────────────────────────────────────────────
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


# ── Static front-end files ───────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "panther_cloud_air.html")

@app.route("/panther_cloud_air.css")
def serve_css():
    return send_from_directory(".", "panther_cloud_air.css", mimetype="text/css")

@app.route("/aircraft_schedule.js")
def serve_schedule():
    return send_from_directory(".", "aircraft_schedule.js", mimetype="application/javascript")


# ── /api/airports ────────────────────────────────────────────────
@app.route("/api/airports")
def api_airports():
    """
    Returns all airports ordered by metro population (descending).
    Each record:
      iata_code, airport_name, city, state, timezone,
      metro_pop, is_hub, gates_available
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
        # Convert tinyint is_hub to bool
        for r in rows:
            r["is_hub"] = bool(r["is_hub"])
        return jsonify(rows)
    finally:
        conn.close()


# ── /api/aircraft ────────────────────────────────────────────────
@app.route("/api/aircraft")
def api_aircraft():
    """
    Returns the full fleet joined with model specs.
    Each record:
      tail_number, status, total_flight_hours,
      model_name, manufacturer, max_passengers,
      seat_config_economy, seat_config_business, seat_config_first,
      cruise_speed_kts, max_range_nm, monthly_lease_usd,
      burn_rate_cruise
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
        # Convert Decimal to float for JSON serialisation
        for r in rows:
            for k in ("total_flight_hours", "cruise_speed_kts", "max_range_nm",
                      "monthly_lease_usd", "burn_rate_cruise"):
                if r[k] is not None:
                    r[k] = float(r[k])
        return jsonify(rows)
    finally:
        conn.close()


# ── /api/pricing ─────────────────────────────────────────────────
@app.route("/api/pricing")
def api_pricing():
    """
    Returns cabin pricing rules from the Pricing_rules table.
    If no rows exist yet, returns sensible defaults.
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


# ── /api/config ──────────────────────────────────────────────────
@app.route("/api/config")
def api_config():
    """
    Returns all System_config rows as a flat key→value dict.
    Example: { "profit_margin": 0.0, "fuel_price_per_gal": 6.19 }
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


# ── /api/login  ──────────────────────────────────────────────────
@app.route("/api/login", methods=["POST"])
def api_login():
    """
    Authenticate a user.
    Body: { "username": "...", "password": "..." }
    Returns: { "ok": true, "user_type": "Admin"|"Employee", "username": "..." }
          or { "ok": false, "error": "..." }
    """
    body = request.get_json(silent=True) or {}
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


# ── /api/bookings ────────────────────────────────────────────────
def _make_ref():
    """Generate a booking reference like PCA-A3X7K."""
    chars = string.ascii_uppercase + string.digits
    return "PCA-" + "".join(random.choices(chars, k=5))


@app.route("/api/bookings", methods=["POST"])
def api_create_booking():
    """
    Record a passenger booking.
    Body: {
      "first_name": "...", "last_name": "...", "email": "...",
      "dob": "YYYY-MM-DD",
      "seat_class": "economy"|"business"|"first",
      "total_price_usd": 123.45
    }
    Returns: { "ok": true, "booking_ref": "PCA-XXXXX" }

    Note: flight_id FK is not populated because the scheduled flights
    live in aircraft_schedule.js rather than the Flights table.
    The Passengers record is stored; a ref code is returned for the UI.
    """
    body = request.get_json(silent=True) or {}
    required = ("first_name", "last_name", "email", "seat_class", "total_price_usd")
    for field in required:
        if not body.get(field):
            return jsonify({"ok": False, "error": f"Missing field: {field}"}), 400

    dob  = body.get("dob", "2000-01-01")   # fallback if front-end omits it
    ref  = _make_ref()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Upsert passenger (email is UNIQUE)
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
    """Look up a passenger by the email stored during booking (ref is decorative)."""
    return jsonify({"ok": True, "booking_ref": ref.upper()})


# ── Run ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
