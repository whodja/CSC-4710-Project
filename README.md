# Panther Cloud Air (PCA)
**CSC 4710 – Database Systems | Spring 2026 | The Future Unemployed**

Panther Cloud Air is a simulated regional US airline. It combines a MariaDB relational database, a Flask REST API, a 14-day operations simulation engine, and a multi-page browser front-end — all running in two Docker containers.

---

## Quick Start

```bash
docker compose up --build
```

Open **http://localhost:5001** in your browser.

| Role     | Username   | Password       |
|----------|------------|----------------|
| Admin    | `admin`    | `Admin@PCA1`   |
| Employee | `employee` | `Employee@PCA1`|

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  Browser                                            │
│  aircraft_schedule.js → shared.js → page scripts   │
│  (static data + API calls)                          │
└────────────────┬────────────────────────────────────┘
                 │ HTTP fetch() to /api/*
┌────────────────▼────────────────────────────────────┐
│  Flask (app.py)          port 5001 → 5000           │
│  serves HTML/JS/CSS + 8 JSON endpoints              │
└────────────────┬────────────────────────────────────┘
                 │ PyMySQL (db.py)
┌────────────────▼────────────────────────────────────┐
│  MariaDB (timetable schema)                         │
│  sql/01–08 create tables; simulate.py writes data   │
└─────────────────────────────────────────────────────┘
```

---

## File-by-File: What Each File Does and How Everything Connects

### Infrastructure

---

#### `docker-compose.yml`
**What it does:** Defines and wires the two containers.

**Pulls from:**
- `Dockerfile` — builds the `web` image (`build: .`)
- `sql/01_aircraft.sql` through `sql/08_users.sql` — bind-mounted into MariaDB at `/docker-entrypoint-initdb.d/`. MariaDB runs them in filename order on first start, creating every table and seeding all data including hashed user passwords.

**Puts data into:**
- The `mariadb` container environment (`MYSQL_ROOT_PASSWORD`, `MYSQL_DATABASE`)
- The `web` container environment (`DB_HOST=mariadb`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`) so `db.py` can connect by service name
- Named volume `project_data:/var/lib/mysql` — persists the database between restarts

---

#### `Dockerfile`
**What it does:** Builds the web container image from `python:3.11-slim`.

**Pulls from:**
- `requirements.txt` — installs Flask and PyMySQL via pip (cached as a separate Docker layer)
- Every `.py`, `.html`, `.js`, `.css` file — copied in via `COPY . .`

**Puts data into:**
- The running container's filesystem at `/app`
- CMD: `python3 app.py` — starts the Flask server

---

#### `entrypoint.sh`
**What it does:** Smarter startup script (alternative to the bare Dockerfile CMD). Retries the DB connection 40 times (3-second delay), checks whether `Sim_final_report` is empty, runs `simulate.py` if no simulation data exists, then hands off to `app.py`.

**Pulls from:** Environment variables (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`)

**Pulls data from DB:** `SELECT COUNT(*) FROM Sim_final_report`

**Triggers:** `simulate.py` (only when `Sim_final_report` is empty), then `app.py`

---

#### `requirements.txt`
**What it does:** Declares Python runtime dependencies: `flask` and `PyMySQL`. Werkzeug (password hashing) is installed automatically as a Flask transitive dependency.

**Pulled by:** `Dockerfile` (`pip install -r requirements.txt`)

---

### Database Schema (sql/)

All eight SQL files are mounted into MariaDB and executed in filename order on first container start. The number prefix controls execution order — a table with a FOREIGN KEY must be created after the table it references.

---

#### `sql/01_aircraft.sql`
**Creates:** `Aircraft_models` and `Aircraft`

**Stores:**
- `Aircraft_models` — 5 model specs (Boeing 737-600/800, Airbus A220-100/300, A350-1000): seats per cabin class, cruise speed (knots), max range (nm), monthly lease cost, burn rate per flight phase (taxi, takeoff, ascent low/high, cruise, descent high/low, landing)
- `Aircraft` — 56 individual tail numbers (N-PCA001 to N-PCA056), each linked to a `model_id`. All start with status `active` and 0 flight hours

**Dependencies (pulls from):** None — first file executed, no foreign keys

**Pulled by:**
- `sql/04_flights.sql` — `aircraft_id` FK
- `simulate.py` `load_aircraft()` — reads both tables via JOIN to get cruise speed, seat counts, and burn rates for every active aircraft

---

#### `sql/02_airports.sql`
**Creates:** `Airports`

**Stores:** 30 US airports — IATA code, name, city, state, timezone, metro population, `is_hub` flag, gate count. Data originally sourced from `airports_clean.csv`.

**Dependencies (pulls from):** None

**Pulled by:**
- `sql/03_flight_distances.sql` — `origin_id` / `destination_id` FK
- `simulate.py` `load_airports()` — reads full table into a dict keyed by IATA code for demand calculation and route lookup
- `app.py` `GET /api/airports` — returns all airports to the browser
- All HTML pages via `loadAirports()` in `shared.js`

---

#### `sql/03_flight_distances.sql`
**Creates:** `Flight_distances`

**Stores:** ~870 directional city-pair routes (hub→spoke, spoke→hub, hub→hub in both directions). Each row: `origin_id`, `destination_id`, `distance_nm`, `is_active`. Distances are stored as nautical miles. Both directions are separate rows because wind makes east-bound and west-bound flight times different.

**Dependencies (pulls from):** `sql/02_airports.sql` — resolves airport IDs via sub-SELECT on `iata_code`

**Pulled by:**
- `sql/04_flights.sql` — `distance_id` FK
- `simulate.py` `load_distances()` — builds two dicts: `(orig, dest) → distance_nm` and `(orig, dest) → dist_id` (the FK used when inserting flight records into Sim_timetable)

---

#### `sql/04_flights.sql`
**Creates:** `Flights` and `Turnaround_time` (no seed data — populated at runtime by `simulate.py`)

**Stores:**
- `Flights` — one row per actual flight: flight number, distance FK, aircraft FK, scheduled and actual departure/arrival timestamps, status
- `Turnaround_time` — per-flight ground time breakdown (disembark 15 min, clean/crew 10 min, board 15 min, door-close 15 min, optional refuel +10 min). Separated from Flights to keep that table from getting too wide.

**Dependencies (pulls from):** `sql/01_aircraft.sql` (`aircraft_id` FK), `sql/03_flight_distances.sql` (`distance_id` FK)

**Pulled by:**
- `sql/05_fuel.sql`, `sql/06_passengers.sql`, `sql/07_pricing.sql` — all have `flight_id` FKs into Flights
- `simulate.py` — writes flight rows here during simulation

---

#### `sql/05_fuel.sql`
**Creates:** `System_config`, `Flight_fuel_logs`, `Flight_fuel_summary`

**Stores:**
- `System_config` — key/value admin settings: `profit_margin` (%), `fuel_price_per_gal` (USD), `taxi_time_min`
- `Flight_fuel_logs` — one row per flight phase (9 phases: taxi_out, takeoff, ascent_low, ascent_high, cruise, descent_high, descent_low, landing, taxi_in) with `duration_min` and `fuel_burned_gal`
- `Flight_fuel_summary` — rolled-up totals per flight: total fuel burned, fuel cost USD, reserve fuel (10% FAA requirement), total fuel loaded

**Dependencies (pulls from):** `sql/04_flights.sql` (`flight_id` FK)

**Pulled by:**
- `simulate.py` — writes all three tables during simulation
- `app.py` `GET /api/config` — reads `System_config` and returns it as a flat key→value JSON dict to the browser
- `admin.html` Config tab — displays the config values

---

#### `sql/06_passengers.sql`
**Creates:** `Passengers` and `Bookings` (no seed data)

**Stores:**
- `Passengers` — one row per person keyed by email (UNIQUE): first name, last name, email, phone, date of birth
- `Bookings` — one row per reservation: booking reference, passenger FK, flight FK, seat class, price paid, booking status

**Dependencies (pulls from):** `sql/04_flights.sql` (`flight_id` FK)

**Pulled by:**
- `app.py` `POST /api/bookings` — upserts into `Passengers` using `ON DUPLICATE KEY UPDATE` on email. Re-booking with the same email updates the existing passenger rather than creating a duplicate.
- `simulate.py` — writes to its own `Sim_passengers` and `Sim_passenger_legs` tables instead (avoids mixing simulated data with live booking data)

---

#### `sql/07_pricing.sql`
**Creates:** `Pricing_rules` and `Ticket_prices`

**Stores:**
- `Pricing_rules` — 3 rows (economy / business / first) with `base_price_usd` and `price_per_nm`. Seeded with defaults; admin can override via UI.
- `Ticket_prices` — computed price per flight × class combination (base + per_nm × distance) × (1 + margin%). Written by `simulate.py`.

**Dependencies (pulls from):** `sql/04_flights.sql` (`flight_id` FK); profit margin pulled from `System_config` in `sql/05_fuel.sql`

**Pulled by:**
- `simulate.py` `load_pricing()` — reads `Pricing_rules` and `System_config.profit_margin` to build the pricing dict used by `calc_fare()`
- `app.py` `GET /api/pricing` — returns fare rules to the browser for display in the Pricing tab
- `shared.js` `loadPricing()` — stores rules in `localStorage` for client-side fare calculation

---

#### `sql/08_users.sql`
**Creates:** `Users`

**Stores:** Admin and Employee accounts with PBKDF2-SHA256 hashed passwords (Werkzeug format). Passwords are hashed — never stored as plaintext. `INSERT IGNORE` means re-running the init scripts never causes a duplicate-key error.

```
admin    / Admin@PCA1    → pbkdf2:sha256:1000000$...
employee / Employee@PCA1 → pbkdf2:sha256:1000000$...
```

**Dependencies (pulls from):** None (no foreign keys)

**Pulled by:**
- `app.py` `POST /api/login` — reads the hashed password and calls `check_password_hash()` to verify the login attempt

---

### Python Backend

---

#### `db.py`
**What it does:** Single function `get_connection()` — opens a PyMySQL `DictCursor` connection to MariaDB. `DictCursor` means every row comes back as a Python dict (column name → value) instead of a plain tuple. `autocommit=True` so every INSERT/UPDATE commits immediately without calling `conn.commit()`.

**Pulls from:** Environment variables (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) with hardcoded local defaults

**Pulled by:**
- `app.py` — imports `get_connection` at the top; every API endpoint calls it, opens a connection, runs its query, then closes in a `finally` block
- `simulate.py` does **not** import `db.py` — it defines its own `get_db()` with `autocommit=False` so entire simulation days can be committed atomically

---

#### `app.py`
**What it does:** Flask REST API. Serves all HTML/JS/CSS files and exposes 8 JSON endpoints.

**Pulls from:** `db.py` (get_connection), Werkzeug (`check_password_hash`), MariaDB tables

**Endpoint → DB table map:**

| Endpoint | Method | Reads From | Writes To |
|----------|--------|------------|-----------|
| `/` | GET | — | — (serves login.html from disk) |
| `/<filename>` | GET | — | — (serves .html/.js/.css) |
| `/api/airports` | GET | `Airports` | — |
| `/api/aircraft` | GET | `Aircraft` JOIN `Aircraft_models` | — |
| `/api/pricing` | GET | `Pricing_rules` | — |
| `/api/config` | GET | `System_config` | — |
| `/api/login` | POST | `Users` | — (read-only verify) |
| `/api/bookings` | POST | — | `Passengers` (upsert on email) |
| `/api/bookings/<ref>` | GET | — | — (echo, no DB) |

**Puts data into browser:** All endpoints return JSON. The browser's `fetch()` calls consume it.

---

#### `simulate.py`
**What it does:** 14-day airline operations simulation engine. This is the most complex file in the project.

**Data it reads from MariaDB (on startup):**

| Function | Reads from | Returns |
|----------|-----------|---------|
| `load_airports()` | `Airports` | Dict: IATA → airport row |
| `load_aircraft()` | `Aircraft` JOIN `Aircraft_models` | Dict: aircraft_id → specs (cruise speed, seat counts, burn rates, monthly lease) |
| `load_distances()` | `Flight_distances` JOIN `Airports` (×2) | Two dicts: `(orig, dest) → nm` and `(orig, dest) → dist_id` |
| `load_pricing()` | `Pricing_rules` + `System_config` | Dict: seat_class → {base, per_nm, margin} |

**Simulation pipeline (runs once per day for 14 days):**

```
Airports + Aircraft_models   →  assign_hub_aircraft()  →  hub_ac dict
                                                                │
Aircraft + Flight_distances  →  generate_timetable()   →  Sim_timetable (DB)
                                                         +  timetable list (memory)
                                                                │
CHALLENGES dict              →  apply_challenge()      →  mutates instances in-place
                                                                │
Demand model (metro_pop)     →  compute_demand()       →  demand dict (memory)
                                                                │
BFS router (_bfs / route_passenger)                    →  itinerary per passenger
                                                                │
calc_fuel_cost() + calc_fare()                         →  revenue & cost per flight
```

**Data it writes to MariaDB:**

| Table | What's stored |
|-------|--------------|
| `Sim_timetable` | One row per hub→spoke and spoke→hub slot. Built once, reused every day as a template. |
| `Sim_flight_instances` | One row per actual flight per day — cloned from timetable with challenge delays/cancellations applied. Includes scheduled vs. actual times, tail number, status, delay reason. |
| `Sim_passengers` | One row per demand passenger: origin, destination, seat class, fare paid, arrived vs. stranded. |
| `Sim_passenger_legs` | One row per flight leg per passenger (multi-leg connections create multiple rows). Links passengers to flight instances. |
| `Sim_daily_report` | Daily P&L: total revenue, fuel cost, landing fees, lease cost, operating cost, profit/loss, passengers carried, load factor. |
| `Sim_final_report` | 14-day aggregate totals. `entrypoint.sh` checks this to decide whether to re-run simulation. |
| `Airport_gate_log` | Gate assignment tracking per departure. |

**Key algorithms:**
- **Hub-spoke timetable:** Each of 55 domestic aircraft flies one round-trip/day from its assigned hub. ATL→14 routes, DFW→14, DEN→14, ORD→13. Flight times calculated with `calc_flight_time()` using bearing + wind factor.
- **Demand model:** `metro_pop × DAILY_FLY_RATE (0.5%) × MARKET_SHARE (2%) × (dest_pop / sum_of_other_pops)`. Gravity model — bigger destination cities attract more passengers.
- **BFS routing:** For each demand passenger, finds the shortest (fewest legs, ≤3) path through that day's flight graph. Retries with progressively looser minimum connection times (30 min → 15 min → 0 min).
- **14-day challenges:** Predefined events (storms, AOG, jet stream) mutate flight instance departure/arrival times and statuses in-place before passengers are routed.
- **Fuel calc:** `burn_rate_cruise × total_flight_time × FUEL_PRICE`. Flight time is phase-by-phase (taxi 20 min fixed + climb 22 min + cruise + descent 18 min) corrected for wind bearing.

---

### JavaScript (Shared / Static)

---

#### `aircraft_schedule.js`
**What it does:** Browser-side static data store. Loaded **first** on every page so its globals are defined before `shared.js` or any page script runs.

**Stores (as in-memory JS globals):**

| Global | Contents |
|--------|----------|
| `FLIGHTS` | Array of ~245 flight objects. Each has: `num`, `tail`, `type`, `from`, `to`, `dep`, `arr`, `seats`, `pax`, and a `CHALLENGES[14]` array of per-day operational modifiers used by the admin dashboard. |
| `AIRCRAFT` | 51 aircraft with tail number, model code, home hub, and ordered daily legs. |
| `AIRPORTS` | 30 static airport objects (fallback if `/api/airports` is unreachable). Overwritten at runtime by `loadAirports()`. |
| `TOO_CLOSE` | Set of 17 canonically-sorted `"IATA1-IATA2"` strings — city pairs within 150 miles that PCA does not serve. |
| `HUBS` | `['ATL', 'DFW', 'DEN', 'ORD', 'JFK']` |
| `DEMAND` | Object: `origin_iata → dest_iata → passengers_per_day`. Mirrors simulate.py's demand model for browser-side display. |
| `ROUTE_STATUS` | Object: `"from-to" → 'direct' | 'connect' | 'unmet'`. Used by `coverage.html`. |

**Pulls from:** Nothing — all data is baked in at development time to match the DB schema and simulate.py constants

**Pulled by:** Every HTML page (loaded first) and `panther_cloud_air_shared.js` (reads `FLIGHTS`, `AIRPORTS`, `HUBS`, etc.)

---

#### `panther_cloud_air_shared.js`
**What it does:** Shared utility library. Loaded on every page after `aircraft_schedule.js`.

**Pulls from (globals defined in aircraft_schedule.js):**
- `FLIGHTS` — `populateSels()` iterates it to fill origin/destination dropdowns
- `AIRPORTS` — overwritten by `loadAirports()` with live DB data
- `HUBS` — populated into the global array after `/api/airports` loads
- `TOO_CLOSE` — `isTooClose()` checks this set before building itineraries

**Calls these Flask API endpoints and stores results:**

| Function | Endpoint | What it stores |
|----------|----------|---------------|
| `loadAirports()` | `GET /api/airports` | Overwrites `AIRPORTS` global; builds `CITY` lookup (IATA → city name); fills `HUBS` array |
| `loadAircraft()` | `GET /api/aircraft` | Stores into `DB_AIRCRAFT` global; used by admin Fleet tab |
| `loadPricing()` | `GET /api/pricing` | Stores rules in `localStorage` as `pca_cpm` for `getCpm()` |

**Reads/writes browser storage:**
- `sessionStorage`: `pca_username`, `pca_role` — login state. Cleared when tab closes.
- `localStorage`: `pca_theme` (dark/light), `pca_cpm` (fare rate slider)

**Functions consumed by page scripts:**
- `checkAuth()` — redirects to `login.html` if not logged in; returns `{username, role}`
- `setupNav(auth)` — shows nav bar, sets username/role badge, hides Admin button for Employee users
- `_completeLogin(username, role)` — saves session to `sessionStorage`, redirects to `admin.html` or `employee.html`
- `go(id)` — universal navigation; handles SPA panel switching inside `book.html`
- `getCpm() / baseFare(legs)` — fare calculation from `localStorage` pricing
- `openMod / closeMod / openSide / closeSide` — modal and side-panel helpers
- `setupTheme / toggleTheme` — dark/light mode via `localStorage`

---

### HTML Pages

Every page loads in this order:
```html
<link href="panther_cloud_air.css">          ← styles
<script src="aircraft_schedule.js">          ← static globals (FIRST)
<script src="panther_cloud_air_shared.js">   ← utilities + API loaders
<script> /* inline page script */ </script>  ← page-specific logic
```

---

#### `login.html`
**What it does:** Application entry point. Presents a username/password form.

**Data flow:**
```
User types credentials
  → POST /api/login  (app.py reads Users table, calls check_password_hash)
  → { ok: true, username, user_type }
  → _completeLogin() saves to sessionStorage
  → redirect to admin.html (Admin) or employee.html (Employee)
```

**Pulls from:** `shared.js` (`setupTheme`, `_completeLogin`, `checkAuth`), `POST /api/login`

---

#### `airports.html`
**What it does:** Sortable table of the full PCA airport network plus a "Too Close" pairs panel.

**Data flow:**
```
init()
  → checkAuth()                         ← sessionStorage
  → loadAirports() → GET /api/airports  ← Airports table
  → build table rows from AIRPORTS global
  → render TOO_CLOSE pairs from aircraft_schedule.js
```

**Pulls from:** `GET /api/airports` (live data), `aircraft_schedule.js` `TOO_CLOSE` set

---

#### `schedule.html`
**What it does:** Flight schedule viewer. Filter by origin, destination, or aircraft model. Shows departure/arrival times, duration, distance, aircraft type, and seat class availability.

**Data flow:**
```
init()
  → checkAuth(), loadAirports() for CITY name map
  → populateSels() iterates FLIGHTS array → fills dropdowns
User selects filters
  → doSearch() filters FLIGHTS array in memory (no API call)
  → baseFare() computes displayed fares from localStorage cpm
```

**Pulls from:** `aircraft_schedule.js` `FLIGHTS` array — **all schedule data is static, no live DB call**

**Why no DB call?** The timetable is baked into `aircraft_schedule.js` at development time. The live `Sim_flight_instances` table contains 14-day simulation history, not the schedule template the browser needs.

---

#### `book.html`
**What it does:** 4-step booking wizard (Search → Class selection → Passenger details → Confirmation). Single-page application — `showPage()` swaps visible panels without a full reload.

**Data flow:**
```
Step 1: Search
  → doSearch() filters FLIGHTS + builds itineraries using isTooClose() guard
  → baseFare() prices each result from localStorage
Step 2: Class selection
  → user picks economy/business/first
Step 3: Passenger details form
  → POST /api/bookings { first_name, last_name, email, dob, seat_class, total_price_usd }
  → app.py: INSERT INTO Passengers ... ON DUPLICATE KEY UPDATE
  → response: { ok: true, booking_ref: "PCA-XXXXX" }
Step 4: Confirmation
  → displays booking_ref from POST response
```

**Pulls from:** `FLIGHTS`, `DEMAND` (aircraft_schedule.js), `loadAirports()`, `baseFare()`, `POST /api/bookings`

**Puts data into:** `Passengers` table (via `POST /api/bookings`)

---

#### `coverage.html`
**What it does:** Route coverage visualisation. OD-pair grid colour-coded by service level (direct / one-stop connection / unmet demand). Also shows demand statistics.

**Data flow:**
```
init()
  → loadAirports() for CITY name map
  → read ROUTE_STATUS from aircraft_schedule.js
  → read DEMAND from aircraft_schedule.js
  → render grid with colour coding
```

**Pulls from:** `aircraft_schedule.js` `ROUTE_STATUS` and `DEMAND` — **no live API call, all static**

---

#### `employee.html`
**What it does:** Read-only employee dashboard. Shows schedule and airport information. Redirects Admins to `admin.html`.

**Data flow:**
```
init()
  → checkAuth() — redirects to login if not authenticated
  → if role === 'Admin' → go('admin')
  → loadAirports(), render FLIGHTS and AIRPORTS data
```

**Pulls from:** `FLIGHTS`, `AIRPORTS` (aircraft_schedule.js), `loadAirports()`, `checkAuth()` (sessionStorage)

---

#### `admin.html`
**What it does:** Full admin dashboard with 5 tabs. The P&L simulation replay runs **entirely in the browser** — no live DB query for the graph.

**Data flow — on init:**
```
Promise.all([loadAirports(), loadAircraft(), loadPricing()])
  → parallel calls to /api/airports, /api/aircraft, /api/pricing
  → populates AIRPORTS/CITY/HUBS, DB_AIRCRAFT, localStorage pricing
```

**Data flow — per tab:**

| Tab | Data source | What it shows |
|-----|-------------|---------------|
| Overview (P&L) | `FLIGHTS[n].CHALLENGES[day]` in aircraft_schedule.js | 14-day P&L replay, computed in browser from static challenge params |
| Schedule | `FLIGHTS` array | All flights with challenge-modified times per selected day |
| Fleet | `DB_AIRCRAFT` (from `GET /api/aircraft`) | Aircraft grouped by model with seat totals and daily lease cost |
| Pricing | `GET /api/pricing` | DB-side fare rules (base price + per-nm rate) |
| Config | `GET /api/config` | System_config values (fuel price, profit margin) |

**Pulls from:** `aircraft_schedule.js` (FLIGHTS with CHALLENGES), `GET /api/aircraft`, `GET /api/pricing`, `GET /api/config`, `GET /api/airports`

---

#### `panther_cloud_air.css`
**What it does:** Single shared stylesheet for all pages. Uses CSS custom properties (variables) so `toggleTheme()` can switch dark/light by toggling one class on `<body>`.

**Pulled by:** Every HTML page via `<link href="panther_cloud_air.css">`

---

### Data & Reference Files

---

#### `airports_clean.csv`
**What it does:** 30-row CSV (IATA code, name, city, state, timezone, metro_pop, is_hub, gates) used when writing the `sql/02_airports.sql` INSERT statements by hand. **Not loaded at runtime** — purely a development reference artifact.

---

## Complete Data Flow Diagram

### Startup Sequence
```
docker compose up --build
  │
  ├── mariadb container starts
  │     └── runs sql/01 → sql/08 in order
  │           01: creates Aircraft_models, Aircraft (56 planes)
  │           02: creates Airports (30 airports)
  │           03: creates Flight_distances (~870 routes)
  │           04: creates Flights, Turnaround_time (empty)
  │           05: creates System_config, Flight_fuel_logs, Flight_fuel_summary
  │           06: creates Passengers, Bookings (empty)
  │           07: creates Pricing_rules (3 rows), Ticket_prices (empty)
  │           08: creates Users, inserts admin + employee with hashed passwords
  │
  └── web container starts (after mariadb healthcheck passes)
        └── python3 app.py (or entrypoint.sh)
              └── if entrypoint.sh: checks Sim_final_report
                    └── if empty: runs simulate.py (see below)
              └── Flask listens on port 5000 → exposed as 5001
```

### Simulation Data Flow
```
simulate.py
  │
  ├── READS from MariaDB
  │     Airports → load_airports() → airports dict (IATA → row)
  │     Aircraft + Aircraft_models → load_aircraft() → specs per aircraft_id
  │     Flight_distances + Airports → load_distances() → dist_map + dist_id
  │     Pricing_rules + System_config → load_pricing() → pricing dict
  │
  ├── COMPUTES in memory
  │     assign_hub_aircraft() → which aircraft flies which hub (55 domestic)
  │     generate_timetable() → hub→spoke round-trips, flight times, fuel
  │     compute_demand() → gravity model: metro_pop × 0.5% × 2% × dest weight
  │
  └── For each of 14 days:
        clone timetable → mutable instances
        apply_challenge() → delays/cancellations/AOG mutated in-place
        INSERT Sim_flight_instances
        BFS route_passenger() per demand pair → itinerary legs
        INSERT Sim_passengers, Sim_passenger_legs
        calc_fare() per passenger → revenue
        calc_fuel_cost() per flight → cost
        INSERT Sim_daily_report (P&L summary)
        conn.commit()  ← atomic per day
  └── INSERT Sim_final_report (14-day totals)
```

### Browser Schedule Data Flow
```
aircraft_schedule.js  (loaded first, static)
  FLIGHTS[245] ──────────────────────────────────────────┐
  AIRPORTS[30] (static fallback)                         │
  HUBS, TOO_CLOSE, DEMAND, ROUTE_STATUS                  │
                                                         ▼
panther_cloud_air_shared.js                     schedule.html
  loadAirports() → GET /api/airports              reads FLIGHTS directly
    → overwrites AIRPORTS global                  no live API call
    → builds CITY map                             filters in browser memory
    → fills HUBS array
  loadAircraft() → GET /api/aircraft
    → DB_AIRCRAFT global → admin Fleet tab
  loadPricing() → GET /api/pricing
    → localStorage pca_cpm → getCpm() → baseFare()
```

### Login & Booking Data Flow
```
login.html
  POST /api/login { username, password }
    → app.py: SELECT password FROM Users WHERE username=?
    → check_password_hash(stored_hash, input_password)
    → { ok: true, username, user_type }
  → _completeLogin() → sessionStorage { pca_username, pca_role }
  → redirect admin.html or employee.html

book.html
  (search + class selection: browser-only, uses FLIGHTS array)
  POST /api/bookings { first_name, last_name, email, dob, seat_class, total_price_usd }
    → app.py: INSERT INTO Passengers ... ON DUPLICATE KEY UPDATE
    → { ok: true, booking_ref: "PCA-XXXXX" }
  → confirmation screen shows booking_ref
```

---

## File Dependency Summary

```
aircraft_schedule.js
  └── consumed by: shared.js, all 8 HTML pages

panther_cloud_air_shared.js
  ├── reads: aircraft_schedule.js globals
  ├── calls: /api/airports, /api/aircraft, /api/pricing
  └── consumed by: all 8 HTML pages

db.py
  └── consumed by: app.py

app.py
  ├── imports: db.py, werkzeug.security
  ├── reads DB: Airports, Aircraft, Aircraft_models, Pricing_rules, System_config, Users
  ├── writes DB: Passengers
  └── serves: all HTML/JS/CSS files + JSON to browser

simulate.py
  ├── reads DB: Airports, Aircraft, Aircraft_models, Flight_distances, Pricing_rules, System_config
  └── writes DB: Sim_timetable, Sim_flight_instances, Sim_passengers,
                  Sim_passenger_legs, Sim_daily_report, Sim_final_report, Airport_gate_log

sql/01_aircraft.sql  → no deps
sql/02_airports.sql  → no deps
sql/03_flight_distances.sql  → needs 02
sql/04_flights.sql           → needs 01, 03
sql/05_fuel.sql              → needs 04
sql/06_passengers.sql        → needs 04
sql/07_pricing.sql           → needs 04, 05
sql/08_users.sql             → no deps
```

---

## Developer Tools

| Script | Command | Output |
|--------|---------|--------|
| Generate code review cheatsheet | `py generate_cheatsheet.py` | `PCA_Code_Review_Cheatsheet.pdf` |
| Generate project documentation  | `py generate_docs.py`       | `PCA_Project_Documentation.pdf` |
| Test DB connection locally      | `py db.py`                  | "Connected to the database successfully!" |
