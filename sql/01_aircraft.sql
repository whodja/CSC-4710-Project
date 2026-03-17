-- ================================================
-- 01_aircraft.sql
-- Defines aircraft model specifications and
-- individual aircraft registered in the
-- Panther Cloud Air fleet.
--
-- Tables:
--   Aircraft_Models  - Specs for each aircraft type
--   Aircraft         - Individual registered aircraft
--
-- ================================================

DROP TABLE IF EXISTS Aircraft;
DROP TABLE IF EXISTS Aircraft_models;

-- ------------------------------------------------
-- Aircraft_Models
-- Stores specifications for each aircraft type.
-- Burn rates are in gallons per minute (gal/min).
-- Cruise speed is 80% operating speed in knots.
-- Seat configuration is defined per model.
-- ------------------------------------------------
CREATE TABLE Aircraft_models (
    model_id                INTEGER         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    manufacturer            VARCHAR(20)     NOT NULL CHECK (manufacturer IN ('Boeing', 'Airbus')),
    model_name              VARCHAR(50)     NOT NULL UNIQUE,
    max_range_nm            DECIMAL(8,2)    NOT NULL CHECK (max_range_nm > 0),
    cruise_speed_kts        DECIMAL(6,2)    NOT NULL CHECK (cruise_speed_kts > 0),
    max_passengers          INTEGER         NOT NULL CHECK (max_passengers > 0),
    seat_config_economy     INTEGER         NOT NULL CHECK (seat_config_economy >= 0),
    seat_config_business    INTEGER         NOT NULL CHECK (seat_config_business >= 0),
    seat_config_first       INTEGER         NOT NULL CHECK (seat_config_first >= 0),
    fuel_capacity_gal       DECIMAL(10,2)   NOT NULL CHECK (fuel_capacity_gal > 0),
    burn_rate_taxi          DECIMAL(8,4)    NOT NULL CHECK (burn_rate_taxi > 0),
    burn_rate_takeoff       DECIMAL(8,4)    NOT NULL CHECK (burn_rate_takeoff > 0),
    burn_rate_ascent_low    DECIMAL(8,4)    NOT NULL CHECK (burn_rate_ascent_low > 0),
    burn_rate_ascent_high   DECIMAL(8,4)    NOT NULL CHECK (burn_rate_ascent_high > 0),
    burn_rate_cruise        DECIMAL(8,4)    NOT NULL CHECK (burn_rate_cruise > 0),
    burn_rate_descent_high  DECIMAL(8,4)    NOT NULL CHECK (burn_rate_descent_high > 0),
    burn_rate_descent_low   DECIMAL(8,4)    NOT NULL CHECK (burn_rate_descent_low > 0),
    burn_rate_landing       DECIMAL(8,4)    NOT NULL CHECK (burn_rate_landing > 0),
    monthly_lease_usd       DECIMAL(10,2)   NOT NULL CHECK (monthly_lease_usd > 0),
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------
-- Aircraft
-- Individual aircraft registered in the fleet.
-- Seat configuration is inherited from Aircraft_Models.
-- ------------------------------------------------
CREATE TABLE Aircraft (
    aircraft_id             INTEGER         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    model_id                INTEGER         NOT NULL,
    tail_number             VARCHAR(10)     NOT NULL UNIQUE,
    status                  VARCHAR(15)     NOT NULL DEFAULT 'active'
                                            CHECK (status IN ('active', 'maintenance', 'retired')),
    total_flight_hours      DECIMAL(10,2)   NOT NULL DEFAULT 0.00 CHECK (total_flight_hours >= 0),
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (model_id) REFERENCES Aircraft_models (model_id)
);

-- ------------------------------------------------
-- Seed Data: Aircraft_models
-- Burn rates in gal/min converted from gal/hour.
-- model_id 1 = Boeing 737-600
-- model_id 2 = Boeing 737-800
-- model_id 3 = Airbus A220-100
-- model_id 4 = Airbus A220-300
-- ------------------------------------------------
INSERT INTO Aircraft_models
    (manufacturer, model_name, max_range_nm, cruise_speed_kts, max_passengers,
     seat_config_economy, seat_config_business, seat_config_first,
     fuel_capacity_gal, burn_rate_taxi, burn_rate_takeoff, burn_rate_ascent_low,
     burn_rate_ascent_high, burn_rate_cruise, burn_rate_descent_high,
     burn_rate_descent_low, burn_rate_landing, monthly_lease_usd)
VALUES
    ('Boeing', 'Boeing 737-600',  3235.00, 364.00, 132, 108, 16,  8, 6875.00, 1.00, 100.00, 40.00, 25.00, 12.50, 6.67, 6.67, 10.00, 245000.00),
    ('Boeing', 'Boeing 737-800',  3060.00, 364.00, 189, 162, 18,  9, 6875.00, 1.00, 110.00, 45.00, 29.17, 14.17, 7.50, 7.50, 11.00, 270000.00),
    ('Airbus', 'Airbus A220-100', 3400.00, 358.00, 133, 108, 16,  9, 5790.00, 0.83,  75.00, 30.00, 20.00,  9.17, 5.00, 5.00,  7.50, 192000.00),
    ('Airbus', 'Airbus A220-300', 3600.00, 376.00, 160, 130, 20, 10, 5790.00, 0.92,  85.00, 35.00, 22.50, 10.42, 5.83, 5.83,  8.50, 228000.00),
    ('Airbus', 'Airbus A350-1000', 8900.00, 488.00, 480, 305, 54, 12, 44346.00, 2.75, 320.00, 128.00, 83.00, 42.00, 20.00, 20.00, 31.00, 290000.00);

-- ------------------------------------------------
-- Seed Data: Aircraft
-- Full fleet of 55 aircraft across 4 models.
-- All aircraft start active with 0 flight hours.
-- ------------------------------------------------

-- Boeing 737-600 (N-PCA001 to N-PCA015)
INSERT INTO Aircraft (model_id, tail_number, status, total_flight_hours) VALUES
    (1, 'N-PCA001', 'active', 0.00),
    (1, 'N-PCA002', 'active', 0.00),
    (1, 'N-PCA003', 'active', 0.00),
    (1, 'N-PCA004', 'active', 0.00),
    (1, 'N-PCA005', 'active', 0.00),
    (1, 'N-PCA006', 'active', 0.00),
    (1, 'N-PCA007', 'active', 0.00),
    (1, 'N-PCA008', 'active', 0.00),
    (1, 'N-PCA009', 'active', 0.00),
    (1, 'N-PCA010', 'active', 0.00),
    (1, 'N-PCA011', 'active', 0.00),
    (1, 'N-PCA012', 'active', 0.00),
    (1, 'N-PCA013', 'active', 0.00),
    (1, 'N-PCA014', 'active', 0.00),
    (1, 'N-PCA015', 'active', 0.00);

-- Boeing 737-800 (N-PCA016 to N-PCA030)
INSERT INTO Aircraft (model_id, tail_number, status, total_flight_hours) VALUES
    (2, 'N-PCA016', 'active', 0.00),
    (2, 'N-PCA017', 'active', 0.00),
    (2, 'N-PCA018', 'active', 0.00),
    (2, 'N-PCA019', 'active', 0.00),
    (2, 'N-PCA020', 'active', 0.00),
    (2, 'N-PCA021', 'active', 0.00),
    (2, 'N-PCA022', 'active', 0.00),
    (2, 'N-PCA023', 'active', 0.00),
    (2, 'N-PCA024', 'active', 0.00),
    (2, 'N-PCA025', 'active', 0.00),
    (2, 'N-PCA026', 'active', 0.00),
    (2, 'N-PCA027', 'active', 0.00),
    (2, 'N-PCA028', 'active', 0.00),
    (2, 'N-PCA029', 'active', 0.00),
    (2, 'N-PCA030', 'active', 0.00);

-- Airbus A220-100 (N-PCA031 to N-PCA042)
INSERT INTO Aircraft (model_id, tail_number, status, total_flight_hours) VALUES
    (3, 'N-PCA031', 'active', 0.00),
    (3, 'N-PCA032', 'active', 0.00),
    (3, 'N-PCA033', 'active', 0.00),
    (3, 'N-PCA034', 'active', 0.00),
    (3, 'N-PCA035', 'active', 0.00),
    (3, 'N-PCA036', 'active', 0.00),
    (3, 'N-PCA037', 'active', 0.00),
    (3, 'N-PCA038', 'active', 0.00),
    (3, 'N-PCA039', 'active', 0.00),
    (3, 'N-PCA040', 'active', 0.00),
    (3, 'N-PCA041', 'active', 0.00),
    (3, 'N-PCA042', 'active', 0.00);

-- Airbus A220-300 (N-PCA043 to N-PCA055)
INSERT INTO Aircraft (model_id, tail_number, status, total_flight_hours) VALUES
    (4, 'N-PCA043', 'active', 0.00),
    (4, 'N-PCA044', 'active', 0.00),
    (4, 'N-PCA045', 'active', 0.00),
    (4, 'N-PCA046', 'active', 0.00),
    (4, 'N-PCA047', 'active', 0.00),
    (4, 'N-PCA048', 'active', 0.00),
    (4, 'N-PCA049', 'active', 0.00),
    (4, 'N-PCA050', 'active', 0.00),
    (4, 'N-PCA051', 'active', 0.00),
    (4, 'N-PCA052', 'active', 0.00),
    (4, 'N-PCA053', 'active', 0.00),
    (4, 'N-PCA054', 'active', 0.00),
    (4, 'N-PCA055', 'active', 0.00);

-- Airbus A350 (N-PCA056)
INSERT INTO Aircraft (model_id, tail_number, status, total_flight_hours) VALUES
    (5, 'N-PCA056', 'active', 0.00);