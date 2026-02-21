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

INSERT INTO Aircraft_Models
    (manufacturer, model_name, max_range_nm, cruise_speed_kts, max_passengers, fuel_capacity_gal, burn_rate_taxi, burn_rate_cruise, burn_rate_descent, monthly_lease_usd)
VALUES
    ('Boeing',  'Boeing 737-600',  3235.00, 364.00, 132, 6875.00, 5.80, 42.00, 17.00, 245000.00),
    ('Boeing',  'Boeing 737-800',  3060.00, 364.00, 189, 6875.00, 6.50, 50.00, 20.00, 270000.00),
    ('Airbus',  'Airbus A220-100', 3400.00, 358.00, 133, 5790.00, 4.80, 34.00, 14.00, 192000.00),
    ('Airbus',  'Airbus A220-300', 3600.00, 376.00, 160, 5790.00, 5.20, 38.00, 16.00, 228000.00);

-- ------------------------------------------------
-- Aircraft
-- Full fleet of 55 aircraft across 4 models.
-- All aircraft start active with 0 flight hours.
-- model_id 1 = Boeing 737-600
-- model_id 2 = Boeing 737-800
-- model_id 3 = Airbus A220-100
-- model_id 4 = Airbus A220-300
-- ------------------------------------------------

-- Boeing 737-600 (N-PCA001 to N-PCA015)
INSERT INTO Aircraft (model_id, tail_number, seat_config_economy, seat_config_business, seat_config_first, status, total_flight_hours)
VALUES
    (1, 'N-PCA001', 108, 16, 8, 'active', 0.00),
    (1, 'N-PCA002', 108, 16, 8, 'active', 0.00),
    (1, 'N-PCA003', 108, 16, 8, 'active', 0.00),
    (1, 'N-PCA004', 108, 16, 8, 'active', 0.00),
    (1, 'N-PCA005', 108, 16, 8, 'active', 0.00),
    (1, 'N-PCA006', 108, 16, 8, 'active', 0.00),
    (1, 'N-PCA007', 108, 16, 8, 'active', 0.00),
    (1, 'N-PCA008', 108, 16, 8, 'active', 0.00),
    (1, 'N-PCA009', 108, 16, 8, 'active', 0.00),
    (1, 'N-PCA010', 108, 16, 8, 'active', 0.00),
    (1, 'N-PCA011', 108, 16, 8, 'active', 0.00),
    (1, 'N-PCA012', 108, 16, 8, 'active', 0.00),
    (1, 'N-PCA013', 108, 16, 8, 'active', 0.00),
    (1, 'N-PCA014', 108, 16, 8, 'active', 0.00),
    (1, 'N-PCA015', 108, 16, 8, 'active', 0.00);

-- Boeing 737-800 (N-PCA016 to N-PCA030)
INSERT INTO Aircraft (model_id, tail_number, seat_config_economy, seat_config_business, seat_config_first, status, total_flight_hours)
VALUES
    (2, 'N-PCA016', 162, 18, 9, 'active', 0.00),
    (2, 'N-PCA017', 162, 18, 9, 'active', 0.00),
    (2, 'N-PCA018', 162, 18, 9, 'active', 0.00),
    (2, 'N-PCA019', 162, 18, 9, 'active', 0.00),
    (2, 'N-PCA020', 162, 18, 9, 'active', 0.00),
    (2, 'N-PCA021', 162, 18, 9, 'active', 0.00),
    (2, 'N-PCA022', 162, 18, 9, 'active', 0.00),
    (2, 'N-PCA023', 162, 18, 9, 'active', 0.00),
    (2, 'N-PCA024', 162, 18, 9, 'active', 0.00),
    (2, 'N-PCA025', 162, 18, 9, 'active', 0.00),
    (2, 'N-PCA026', 162, 18, 9, 'active', 0.00),
    (2, 'N-PCA027', 162, 18, 9, 'active', 0.00),
    (2, 'N-PCA028', 162, 18, 9, 'active', 0.00),
    (2, 'N-PCA029', 162, 18, 9, 'active', 0.00),
    (2, 'N-PCA030', 162, 18, 9, 'active', 0.00);

-- Airbus A220-100 (N-PCA031 to N-PCA042)
INSERT INTO Aircraft (model_id, tail_number, seat_config_economy, seat_config_business, seat_config_first, status, total_flight_hours)
VALUES
    (3, 'N-PCA031', 108, 16, 9, 'active', 0.00),
    (3, 'N-PCA032', 108, 16, 9, 'active', 0.00),
    (3, 'N-PCA033', 108, 16, 9, 'active', 0.00),
    (3, 'N-PCA034', 108, 16, 9, 'active', 0.00),
    (3, 'N-PCA035', 108, 16, 9, 'active', 0.00),
    (3, 'N-PCA036', 108, 16, 9, 'active', 0.00),
    (3, 'N-PCA037', 108, 16, 9, 'active', 0.00),
    (3, 'N-PCA038', 108, 16, 9, 'active', 0.00),
    (3, 'N-PCA039', 108, 16, 9, 'active', 0.00),
    (3, 'N-PCA040', 108, 16, 9, 'active', 0.00),
    (3, 'N-PCA041', 108, 16, 9, 'active', 0.00),
    (3, 'N-PCA042', 108, 16, 9, 'active', 0.00);

-- Airbus A220-300 (N-PCA043 to N-PCA055)
INSERT INTO Aircraft (model_id, tail_number, seat_config_economy, seat_config_business, seat_config_first, status, total_flight_hours)
VALUES
    (4, 'N-PCA043', 108, 16, 9, 'active', 0.00),
    (4, 'N-PCA044', 108, 16, 9, 'active', 0.00),
    (4, 'N-PCA045', 108, 16, 9, 'active', 0.00),
    (4, 'N-PCA046', 108, 16, 9, 'active', 0.00),
    (4, 'N-PCA047', 108, 16, 9, 'active', 0.00),
    (4, 'N-PCA048', 108, 16, 9, 'active', 0.00),
    (4, 'N-PCA049', 108, 16, 9, 'active', 0.00),
    (4, 'N-PCA050', 108, 16, 9, 'active', 0.00),
    (4, 'N-PCA051', 108, 16, 9, 'active', 0.00),
    (4, 'N-PCA052', 108, 16, 9, 'active', 0.00),
    (4, 'N-PCA053', 108, 16, 9, 'active', 0.00),
    (4, 'N-PCA054', 108, 16, 9, 'active', 0.00),
    (4, 'N-PCA055', 108, 16, 9, 'active', 0.00);