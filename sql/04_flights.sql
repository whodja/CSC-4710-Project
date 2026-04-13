-- ================================================
-- 04_flights.sql
-- Defines flight operations and turnaround time
-- tracking for Panther Cloud Air.
--
-- Tables:
--   Flights          - Scheduled and completed flights
--   Turnaround_time  - Ground time breakdown per flight
--
-- Dependencies (must run first):
--   01_aircraft.sql        - Aircraft table
--   03_flight_distances.sql - FlightDistances table
--
-- ================================================

DROP TABLE IF EXISTS Turnaround_time;
DROP TABLE IF EXISTS Flights;

-- ------------------------------------------------
-- Flights
-- Tracks each flight operated by Panther Cloud Air.
-- flight_number format: PCA-XXXX (e.g. PCA-1042)
-- status: scheduled, boarding, airborne, landed,
--         cancelled, diverted
-- distance_id references FlightDistances table
-- ------------------------------------------------
CREATE TABLE Flights (
    flight_id               INTEGER         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    flight_number           VARCHAR(10)     NOT NULL UNIQUE,
    distance_id             INTEGER         NOT NULL,
    aircraft_id             INTEGER         NOT NULL,
    scheduled_departure     DATETIME        NOT NULL,
    scheduled_arrival       DATETIME        NOT NULL,
    actual_departure        DATETIME,
    actual_arrival          DATETIME,
    status                  VARCHAR(15)     NOT NULL DEFAULT 'scheduled'
                                            CHECK (status IN ('scheduled', 'boarding', 'airborne', 'landed', 'cancelled', 'diverted')),
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (aircraft_id) REFERENCES Aircraft (aircraft_id),
    FOREIGN KEY (distance_id) REFERENCES Flight_distances (id)
);

-- ------------------------------------------------
-- Turnaround_time
-- Tracks ground time breakdown for each flight
-- based on Panther Cloud Air turnaround standards.
--
-- Standard times (minutes):
--   Disembark passengers : 15 (always)
--   Clean & change crew  : 10 (always)
--   Board passengers     : 15 (always)
--   Door close           : 15 (always)
--   Refueling            : +10 (only if needed)
--   Minimum ground time  : 55 (no refuel)
--                          65 (with refuel)
-- ------------------------------------------------
CREATE TABLE Turnaround_time (
    turnaround_id       INTEGER         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    flight_id           INTEGER         NOT NULL UNIQUE,
    disembark_min       INTEGER         NOT NULL DEFAULT 15,
    clean_crew_min      INTEGER         NOT NULL DEFAULT 10,
    board_min           INTEGER         NOT NULL DEFAULT 15,
    door_close_min      INTEGER         NOT NULL DEFAULT 15,
    refuel_required     BOOLEAN         NOT NULL DEFAULT FALSE,
    refuel_min          INTEGER         NOT NULL DEFAULT 0 CHECK (refuel_min IN (0, 10)),
    total_ground_min    INTEGER         NOT NULL,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (flight_id) REFERENCES Flights (flight_id)
);