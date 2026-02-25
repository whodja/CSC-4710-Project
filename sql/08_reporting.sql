
-- NOT SURE IF WE ACTUALLY NEED THIS OR NOT BUT LEAVING IT FOR NOW
-- Claude code, not very readable and I think there's an easier way to do this but I can't do that right now



-- ================================================
-- 08_reporting.sql
-- Defines reporting views for Panther Cloud Air.
-- Views calculate live from underlying tables.
--
-- Views:
--   Route_profitability    - Revenue and costs per route
--   Aircraft_profitability - Revenue and costs per aircraft
-- ================================================

-- ------------------------------------------------
-- Route_profitability
-- Shows revenue, fuel cost, and net profit per
-- route (origin -> destination pair).
--
-- revenue:        sum of all ticket prices sold
-- fuel_cost:      sum of fuel costs for all flights
-- net_profit:     revenue - fuel_cost
-- total_flights:  number of flights on this route
-- ------------------------------------------------
CREATE OR REPLACE VIEW Route_profitability AS
SELECT
    a_origin.iata_code                          AS origin_iata,
    a_origin.city                               AS origin_city,
    a_dest.iata_code                            AS destination_iata,
    a_dest.city                                 AS destination_city,
    fd.distance_nm                              AS distance_nm,
    COUNT(DISTINCT f.flight_id)                 AS total_flights,
    COALESCE(SUM(tp.calculated_price), 0)       AS total_revenue,
    COALESCE(SUM(ffs.fuel_cost_usd), 0)         AS total_fuel_cost,
    COALESCE(SUM(tp.calculated_price), 0)
        - COALESCE(SUM(ffs.fuel_cost_usd), 0)  AS net_profit
FROM FlightDistances fd
JOIN Airports a_origin   ON fd.origin_id      = a_origin.airport_id
JOIN Airports a_dest     ON fd.destination_id = a_dest.airport_id
LEFT JOIN Flights f      ON f.distance_id     = fd.id
    AND f.status = 'landed'
LEFT JOIN Ticket_prices tp   ON tp.flight_id  = f.flight_id
LEFT JOIN Flight_fuel_summary ffs ON ffs.flight_id = f.flight_id
GROUP BY
    fd.id,
    a_origin.iata_code,
    a_origin.city,
    a_dest.iata_code,
    a_dest.city,
    fd.distance_nm;

-- ------------------------------------------------
-- Aircraft_profitability
-- Shows revenue, fuel cost, lease cost, and net
-- profit per individual aircraft.
--
-- lease_cost:  monthly_lease_usd (fixed per model)
-- revenue:     sum of all tickets for flights on
--              this aircraft
-- fuel_cost:   sum of fuel costs for this aircraft
-- net_profit:  revenue - fuel_cost - lease_cost
-- ------------------------------------------------
CREATE OR REPLACE VIEW Aircraft_profitability AS
SELECT
    a.aircraft_id                                       AS aircraft_id,
    a.tail_number                                       AS tail_number,
    am.model_name                                       AS model_name,
    a.status                                            AS status,
    a.total_flight_hours                                AS total_flight_hours,
    COUNT(DISTINCT f.flight_id)                         AS total_flights,
    am.monthly_lease_usd                                AS monthly_lease_usd,
    COALESCE(SUM(tp.calculated_price), 0)               AS total_revenue,
    COALESCE(SUM(ffs.fuel_cost_usd), 0)                 AS total_fuel_cost,
    COALESCE(SUM(tp.calculated_price), 0)
        - COALESCE(SUM(ffs.fuel_cost_usd), 0)
        - am.monthly_lease_usd                          AS net_profit
FROM Aircraft a
JOIN Aircraft_Models am      ON a.model_id       = am.model_id
LEFT JOIN Flights f          ON f.aircraft_id    = a.aircraft_id
    AND f.status = 'landed'
LEFT JOIN Ticket_prices tp   ON tp.flight_id     = f.flight_id
LEFT JOIN Flight_fuel_summary ffs ON ffs.flight_id = f.flight_id
GROUP BY
    a.aircraft_id,
    a.tail_number,
    am.model_name,
    a.status,
    a.total_flight_hours,
    am.monthly_lease_usd;