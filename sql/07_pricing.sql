-- ================================================
-- Graham McCabe 
-- CSC-4810
-- 07_pricing.sql
-- Defines pricing rules and calculated ticket
-- prices for Panther Cloud Air.
--
-- Tables:
--   Pricing_rules  - Admin-defined base pricing per seat class
--   Ticket_prices  - Calculated prices per flight (runtime)
--
-- Note: profit_margin is stored in System_config (05_fuel.sql)
--
-- ================================================

DROP TABLE IF EXISTS Ticket_prices;
DROP TABLE IF EXISTS Pricing_rules;

-- ------------------------------------------------
-- Pricing_rules
-- Stores base pricing per seat class.
-- Set by admin via the UI.
--
-- base_price_usd: starting price before distance
-- price_per_nm: additional cost per nautical mile
-- Profit margin is pulled from System_config.
-- ------------------------------------------------
CREATE TABLE Pricing_rules (
    pricing_id      INTEGER         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    seat_class      VARCHAR(10)     NOT NULL CHECK (seat_class IN ('economy', 'business', 'first')),
    base_price_usd  DECIMAL(10,2)   NOT NULL CHECK (base_price_usd >= 0),
    price_per_nm    DECIMAL(8,4)    NOT NULL CHECK (price_per_nm >= 0),
    last_updated    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE (seat_class)
);

-- ------------------------------------------------
-- Ticket_prices
-- Calculated ticket price per flight and seat class.
-- Populated at runtime when a flight is scheduled.
--
-- Formula:
--   calculated_price = (base_price_usd + price_per_nm * distance_nm)
--                      * (1 + profit_margin / 100)
--   where profit_margin comes from System_config
-- ------------------------------------------------
CREATE TABLE Ticket_prices (
    ticket_price_id     INTEGER         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    flight_id           INTEGER         NOT NULL,
    seat_class          VARCHAR(10)     NOT NULL CHECK (seat_class IN ('economy', 'business', 'first')),
    calculated_price    DECIMAL(10,2)   NOT NULL CHECK (calculated_price >= 0),
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (flight_id) REFERENCES Flights (flight_id),
    UNIQUE (flight_id, seat_class)
);

-- ------------------------------------------------
-- Seed Data: Pricing_rules
-- Default pricing per seat class.
-- Admin can update these via the UI.
-- ------------------------------------------------
INSERT INTO Pricing_rules (seat_class, base_price_usd, price_per_nm)
VALUES
    ('economy',   49.99, 0.1100),
    ('business', 149.99, 0.2200),
    ('first',    299.99, 0.3500);