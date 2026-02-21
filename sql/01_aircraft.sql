-- ================================================
-- 01_aircraft.sql
-- Defines aircraft model specifications and
-- individual aircraft registered
--
-- Tables:
--   Aircraft_Models  - Specs for each aircraft type
--   Aircraft         - Individual registered aircraft
--
-- ================================================

DROP TABLE IF EXISTS Aircraft;
DROP TABLE IF EXISTS Aircraft_Models;

-- ------------------------------------------------
-- Aircraft_Models Table 
-- Stores specifications for each aircraft type.
-- Boeing 737-800 and Airbus A220 are the two
-- primary models for Panther Cloud Air.
-- ------------------------------------------------
CREATE TABLE Aircraft_Models (
    model_id            INTEGER         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    manufacturer        VARCHAR(10)     NOT NULL CHECK (manufacturer IN ('Boeing', 'Airbus')),
    model_name          VARCHAR(50)     NOT NULL UNIQUE,
    max_range_nm        DECIMAL(8,2)    NOT NULL CHECK (max_range_nm > 0),
    cruise_speed_kts    DECIMAL(6,2)    NOT NULL CHECK (cruise_speed_kts > 0),
    max_passengers      INTEGER         NOT NULL CHECK (max_passengers > 0),
    fuel_capacity_gal   DECIMAL(10,2)   NOT NULL CHECK (fuel_capacity_gal > 0),
    burn_rate_taxi      DECIMAL(8,2)    NOT NULL CHECK (burn_rate_taxi > 0),
    burn_rate_cruise    DECIMAL(8,2)    NOT NULL CHECK (burn_rate_cruise > 0),
    burn_rate_descent   DECIMAL(8,2)    NOT NULL CHECK (burn_rate_descent > 0),
    monthly_lease_usd   DECIMAL(10,2)   NOT NULL CHECK (monthly_lease_usd > 0),
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------
-- Aircraft Table
-- Individual aircraft registered in the fleet.
-- Each aircraft references a model from
-- Aircraft_Models and tracks its own seat
-- configuration and flight hours.
-- ------------------------------------------------
CREATE TABLE Aircraft (
    aircraft_id             INTEGER         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    model_id                INTEGER         NOT NULL,
    tail_number             VARCHAR(10)     NOT NULL UNIQUE,
    seat_config_economy     INTEGER         NOT NULL CHECK (seat_config_economy >= 0),
    seat_config_business    INTEGER         NOT NULL CHECK (seat_config_business >= 0),
    seat_config_first       INTEGER         NOT NULL CHECK (seat_config_first >= 0),
    status                  VARCHAR(15)     NOT NULL DEFAULT 'active'
                                            CHECK (status IN ('active', 'maintenance', 'retired')),
    total_flight_hours      DECIMAL(10,2)   NOT NULL DEFAULT 0.00 CHECK (total_flight_hours >= 0),
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (model_id) REFERENCES Aircraft_Models (model_id)
);