# Panther Cloud Air — Database Setup

## Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

## Project Structure
```
project/
├── docker-compose.yml
└── sql/
    ├── 01_aircraft.sql         # Aircraft_Models, Aircraft tables
    ├── 02_airports.sql         # Airports table
    ├── 03_flight_distances.sql # FlightDistances table
    ├── 04_flights.sql          # Flights, Turnaround_time tables
    ├── 08_seed.sql             # All static data (aircraft, airports)
```

## Starting the Database

```bash
docker compose up -d
```

## Resetting the Database
If you need a clean slate (e.g. after schema changes):

```bash
docker compose down -v
docker compose up -d
```

> **Warning:** The `-v` flag deletes all data. Only run this if you want to start fresh.

## Accessing the Database

### Terminal (MariaDB shell)
```bash
docker exec -it mariadb-compose mariadb -u root -pTheFutureUnemployed
```

Then select the database:
```sql
USE timetable;
SHOW TABLES;
```