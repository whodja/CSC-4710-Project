-- ================================================
-- Graham McCabe
-- 02_airports.sql
-- Defines and populates the Airports table for
-- Panther Cloud Air's 30-airport US network.
--
-- Tables:
--   Airports - All operating airports
-- ================================================

DROP TABLE IF EXISTS Airports;

-- ------------------------------------------------
-- Airports
-- Each airport in the PCA network.
-- ------------------------------------------------
CREATE TABLE Airports (
    airport_id      INTEGER         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    iata_code       VARCHAR(3)      NOT NULL UNIQUE,
    airport_name    VARCHAR(100)    NOT NULL,
    city            VARCHAR(50)     NOT NULL,
    state           VARCHAR(50)     NOT NULL,
    timezone        VARCHAR(50)     NOT NULL,
    metro_pop       INTEGER         NOT NULL CHECK (metro_pop > 0),
    is_hub          BOOLEAN         NOT NULL DEFAULT FALSE,
    gates_available INTEGER         NOT NULL CHECK (gates_available > 0)
);

-- ------------------------------------------------
-- Seed Data: Hub Airports (is_hub=TRUE, 11 gates)
-- ATL, DFW, DEN, ORD serve as the four routing hubs
-- ------------------------------------------------
INSERT INTO Airports (iata_code, airport_name, city, state, timezone, metro_pop, is_hub, gates_available) VALUES
('ATL', 'Hartsfield-Jackson Atlanta International', 'Atlanta',  'Georgia',  'America/New_York',  6411000, TRUE, 11),
('DFW', 'Dallas/Fort Worth International',          'Dallas',   'Texas',    'America/Chicago',   7637000, TRUE, 11),
('DEN', 'Denver International',                     'Denver',   'Colorado', 'America/Denver',    2963000, TRUE, 11),
('ORD', 'O''Hare International',                    'Chicago',  'Illinois', 'America/Chicago',   9442000, TRUE, 11);

-- ------------------------------------------------
-- Seed Data: Northeast / Mid-Atlantic Spoke Airports
-- ------------------------------------------------
INSERT INTO Airports (iata_code, airport_name, city, state, timezone, metro_pop, is_hub, gates_available) VALUES
('JFK', 'John F. Kennedy International',      'New York',     'New York',             'America/New_York', 19500000, FALSE, 5),
('EWR', 'Newark Liberty International',       'Newark',       'New Jersey',           'America/New_York', 19500000, FALSE, 5),
('LGA', 'LaGuardia',                          'New York',     'New York',             'America/New_York', 19500000, FALSE, 5),
('BOS', 'Logan International',                'Boston',       'Massachusetts',        'America/New_York',  4919000, FALSE, 5),
('PHL', 'Philadelphia International',         'Philadelphia', 'Pennsylvania',         'America/New_York',  6245000, FALSE, 5),
('DCA', 'Ronald Reagan Washington National',  'Washington',   'District of Columbia', 'America/New_York',  6385000, FALSE, 5),
('BWI', 'Baltimore/Washington International', 'Baltimore',    'Maryland',             'America/New_York',  6385000, FALSE, 5),
('IAD', 'Washington Dulles International',    'Washington',   'District of Columbia', 'America/New_York',  6385000, FALSE, 5),
('DTW', 'Detroit Metropolitan Wayne County',  'Detroit',      'Michigan',             'America/Detroit',   4365000, FALSE, 4),
('MSP', 'Minneapolis-St. Paul International', 'Minneapolis',  'Minnesota',            'America/Chicago',   3690000, FALSE, 4);

-- ------------------------------------------------
-- Seed Data: Southeast / Florida Spoke Airports
-- ------------------------------------------------
INSERT INTO Airports (iata_code, airport_name, city, state, timezone, metro_pop, is_hub, gates_available) VALUES
('MIA', 'Miami International',                        'Miami',           'Florida',        'America/New_York', 6183000, FALSE, 5),
('FLL', 'Fort Lauderdale-Hollywood International',    'Fort Lauderdale', 'Florida',        'America/New_York', 6183000, FALSE, 5),
('MCO', 'Orlando International',                      'Orlando',         'Florida',        'America/New_York', 2673000, FALSE, 3),
('TPA', 'Tampa International',                        'Tampa',           'Florida',        'America/New_York', 3342000, FALSE, 3),
('CLT', 'Charlotte Douglas International',            'Charlotte',       'North Carolina', 'America/New_York', 2797000, FALSE, 3);

-- ------------------------------------------------
-- Seed Data: South / Southwest Spoke Airports
-- ------------------------------------------------
INSERT INTO Airports (iata_code, airport_name, city, state, timezone, metro_pop, is_hub, gates_available) VALUES
('IAH', 'George Bush Intercontinental',         'Houston',   'Texas',    'America/Chicago',    7122000, FALSE, 5),
('AUS', 'Austin-Bergstrom International',        'Austin',    'Texas',    'America/Chicago',    2352000, FALSE, 2),
('PHX', 'Phoenix Sky Harbor International',      'Phoenix',   'Arizona',  'America/Phoenix',    4948000, FALSE, 5),
('LAS', 'Harry Reid International',              'Las Vegas', 'Nevada',   'America/Los_Angeles',2265000, FALSE, 2);

-- ------------------------------------------------
-- Seed Data: West Coast Airports
-- ------------------------------------------------
INSERT INTO Airports (iata_code, airport_name, city, state, timezone, metro_pop, is_hub, gates_available) VALUES
('LAX', 'Los Angeles International',    'Los Angeles',   'California', 'America/Los_Angeles', 13200000, FALSE, 5),
('SAN', 'San Diego International',      'San Diego',     'California', 'America/Los_Angeles',  3269000, FALSE, 3),
('SFO', 'San Francisco International',  'San Francisco', 'California', 'America/Los_Angeles',  4623000, FALSE, 5),
('SEA', 'Seattle-Tacoma International', 'Seattle',       'Washington', 'America/Los_Angeles',  4012000, FALSE, 4),
('PDX', 'Portland International',       'Portland',      'Oregon',     'America/Los_Angeles',  2512000, FALSE, 3);

-- ------------------------------------------------
-- Seed Data: Mountain / Pacific Airports.
-- ------------------------------------------------
INSERT INTO Airports (iata_code, airport_name, city, state, timezone, metro_pop, is_hub, gates_available) VALUES
('SLC', 'Salt Lake City International', 'Salt Lake City', 'Utah',   'America/Denver',   1257000, FALSE, 1),
('HNL', 'Honolulu International',       'Honolulu',       'Hawaii',  'Pacific/Honolulu',  974000, FALSE, 1);
