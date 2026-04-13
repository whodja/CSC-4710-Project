-- ================================================
-- Graham McCabe 
-- CSC-4810
-- 05_fuel.sql
-- Defines fuel logging and summary tables for
-- Panther Cloud Air flight operations.
--
-- Tables:
--   Flight_fuel_logs     - Per-phase fuel burn tracking
--   Flight_fuel_summary  - Total fuel summary per flight
--   System_config        - Admin-controlled simulation settings
-- ================================================

DROP TABLE IF EXISTS Flight_fuel_summary;
DROP TABLE IF EXISTS Flight_fuel_logs;
DROP TABLE IF EXISTS System_config;

-- ------------------------------------------------
-- System_config
-- Stores admin-controlled simulation-wide settings.
-- Fuel price and taxi time are set here.
-- profit_margin is a percentage (e.g. 15.00 = 15%)
-- ------------------------------------------------
CREATE TABLE System_config (
    config_id       INTEGER         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    config_key      VARCHAR(50)     NOT NULL UNIQUE,
    config_value    DECIMAL(10,2)   NOT NULL,
    last_updated    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ------------------------------------------------
-- Flight_fuel_logs
-- Tracks fuel burn for each phase of a flight.
-- One record per phase per flight.
--
-- Phases: taxi_out, takeoff, ascent_low, ascent_high,
--         cruise, descent_high, descent_low, landing,
--         taxi_in
-- duration_min: how long the phase lasted
-- fuel_burned_gal: burn_rate * duration_min
-- ------------------------------------------------
CREATE TABLE Flight_fuel_logs (
    fuel_log_id         INTEGER         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    flight_id           INTEGER         NOT NULL,
    phase               VARCHAR(15)     NOT NULL CHECK (phase IN (
                            'taxi_out', 'takeoff', 'ascent_low', 'ascent_high',
                            'cruise', 'descent_high', 'descent_low', 'landing', 'taxi_in'
                        )),
    duration_min        DECIMAL(8,2)    NOT NULL CHECK (duration_min >= 0),
    fuel_burned_gal     DECIMAL(10,2)   NOT NULL CHECK (fuel_burned_gal >= 0),
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (flight_id) REFERENCES Flights (flight_id),
    UNIQUE (flight_id, phase)
);

-- ------------------------------------------------
-- Flight_fuel_summary
-- Rolls up all phase logs into a single record
-- per flight.
--
-- total_fuel_burned_gal: sum of all phase burns
-- fuel_cost_usd: total_fuel_burned * fuel_price_per_gal
-- reserve_fuel_gal: 10% of total burned (FAA requirement)
-- total_fuel_loaded_gal: burned + reserve
-- ------------------------------------------------
CREATE TABLE Flight_fuel_summary (
    summary_id              INTEGER         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    flight_id               INTEGER         NOT NULL UNIQUE,
    total_fuel_burned_gal   DECIMAL(10,2)   NOT NULL CHECK (total_fuel_burned_gal >= 0),
    fuel_cost_usd           DECIMAL(10,2)   NOT NULL CHECK (fuel_cost_usd >= 0),
    reserve_fuel_gal        DECIMAL(10,2)   NOT NULL CHECK (reserve_fuel_gal >= 0),
    total_fuel_loaded_gal   DECIMAL(10,2)   NOT NULL CHECK (total_fuel_loaded_gal >= 0),
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (flight_id) REFERENCES Flights (flight_id)
);

-- ------------------------------------------------
-- Seed Data: System_config
-- Default simulation settings.
-- Fuel price based on 2024 US average jet fuel.
-- Taxi time in minutes (applied to taxi_out/taxi_in).
-- Profit margin defaults to 0 until admin sets it.
-- ------------------------------------------------
INSERT INTO System_config (config_key, config_value) VALUES
    ('profit_margin',       0.00);