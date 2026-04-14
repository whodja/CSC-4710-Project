"""
Graham McCabe
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


# CORS helper
@app.after_request
def add_cors_headers(response):
    """
    Attach CORS headers to every response so the front-end can reach the API
    regardless of how the HTML files are served (localhost, Docker, or file://).
    The permissive '*' origin is intentional. 
    """
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


# front-end file serving
@app.route("/")
def index():
    """Serve the login page as the application root."""
    return send_from_directory(".", "login.html")


@app.route("/<path:filename>")
def serve_static(filename):
    """
    Serve any .html, .js, or .css file that lives in the project root directory.
    """
    allowed = ('.html', '.js', '.css')
    if '/' not in filename and any(filename.endswith(ext) for ext in allowed):
        return send_from_directory(".", filename)
    return "Not found", 404


# GET /api/airports 
@app.route("/api/airports")
def api_airports():
    """
    Return the full PCA airport network ordered by metro population (highest first).

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


# GET /api/aircraft
@app.route("/api/aircraft")
def api_aircraft():
    """
    Return the full fleet joined with aircraft model specifications.
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


# GET /api/pricing
@app.route("/api/pricing")
def api_pricing():
    """
    Return cabin pricing rules from the Pricing_rules table.
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


# GET /api/config
@app.route("/api/config")
def api_config():
    """
    Return all System_config rows as a flat key→value dict.
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


# POST /api/login
@app.route("/api/login", methods=["POST"])
def api_login():
    """
    Authenticate a user against the Users table.
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


# POST /api/bookings
def _make_ref():
    """
    Generate a booking reference code in the format PCA-XXXXX.
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
            # insert new passenger or update name/DOB if email already exists
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
    """
    return jsonify({"ok": True, "booking_ref": ref.upper()})


# Entry point
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
