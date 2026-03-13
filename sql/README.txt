# Panther Cloud Air — Database Setup

## Starting the Database

run: docker compose up -d


## Resetting the Database
If you need a clean slate (e.g. after schema changes):

run:
docker compose down -v
docker compose up -d


> **Warning:** The `-v` flag deletes all data. Only run this if you want to start fresh.

## Accessing the Database

### Terminal (MariaDB shell)
run docker exec -it mariadb-compose mariadb -u root -pTheFutureUnemployed


Then select the database:
USE timetable;
SHOW TABLES;
