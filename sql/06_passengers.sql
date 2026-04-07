-- ================================================
-- 06_passengers.sql
-- Defines passenger and booking tables for
-- Panther Cloud Air.
--
-- Tables:
--   Passengers - Personal info for each passenger
--   Bookings   - Flight reservations per passenger
--
-- ================================================

DROP TABLE IF EXISTS Bookings;
DROP TABLE IF EXISTS Passengers;

-- ------------------------------------------------
-- Passengers
-- Stores personal information for each passenger.
-- One record per person regardless of how many
-- flights they have booked.
-- ------------------------------------------------
CREATE TABLE Passengers (
    passenger_id    INTEGER         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    first_name      VARCHAR(50)     NOT NULL,
    last_name       VARCHAR(50)     NOT NULL,
    email           VARCHAR(100)    NOT NULL UNIQUE,
    phone           VARCHAR(20),
    date_of_birth   DATE            NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------
-- Bookings
-- Stores flight reservations for each passenger.
-- A passenger can have many bookings.
-- booking_ref is a human-readable reference code.
-- booking_status: confirmed, cancelled, completed
-- seat_class: economy, business, first
-- ------------------------------------------------
CREATE TABLE Bookings (
    booking_id      INTEGER         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    booking_ref     VARCHAR(10)     NOT NULL UNIQUE,
    passenger_id    INTEGER         NOT NULL,
    flight_id       INTEGER         NOT NULL,
    seat_class      VARCHAR(10)     NOT NULL CHECK (seat_class IN ('economy', 'business', 'first')),
    seat_number     VARCHAR(5),
    price_paid      DECIMAL(10,2)   NOT NULL CHECK (price_paid >= 0),
    booking_status  VARCHAR(15)     NOT NULL DEFAULT 'confirmed'
                                    CHECK (booking_status IN ('confirmed', 'cancelled', 'completed')),
    booked_at       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cancelled_at    DATETIME,

    FOREIGN KEY (passenger_id) REFERENCES Passengers (passenger_id),
    FOREIGN KEY (flight_id)    REFERENCES Flights (flight_id)
);