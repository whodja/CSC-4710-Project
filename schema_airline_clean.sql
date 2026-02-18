-- SQLite schema for your airline distance data (cleaned)
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS FlightDistances;
DROP TABLE IF EXISTS Airports;

CREATE TABLE Airports (
  airport_id INTEGER PRIMARY KEY,
  airport_name TEXT NOT NULL UNIQUE
);

CREATE TABLE FlightDistances (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  origin_id INTEGER NOT NULL,
  destination_id INTEGER NOT NULL,
  distance INTEGER NOT NULL CHECK(distance > 0),
  FOREIGN KEY (origin_id) REFERENCES Airports(airport_id),
  FOREIGN KEY (destination_id) REFERENCES Airports(airport_id),
  UNIQUE(origin_id, destination_id)
);
