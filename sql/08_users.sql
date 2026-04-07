-- ================================================
-- 08_users.sql
-- Defines system users for Panther Airs.
--
-- Tables:
--   Users  - Stores login credentials and role
--            for all system users
--
-- ================================================

DROP TABLE IF EXISTS Users;

-- ------------------------------------------------
-- Users
-- Stores all registered system users.
--
-- username:  Unique login identifier
-- password:  Hashed password (bcrypt recommended)
-- user_type: Role restricted to 'Admin' or 'Employee'
-- ------------------------------------------------
CREATE TABLE Users (
    id          INTEGER         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(50)     NOT NULL UNIQUE,
    password    VARCHAR(255)    NOT NULL,
    user_type   ENUM('Admin', 'Employee') NOT NULL
);

-- ------------------------------------------------
-- Seed Data: Users
-- Hashed passwords are inserted at container startup
-- by seed_users.py using werkzeug.security (PBKDF2-SHA256).
-- Do NOT insert plaintext passwords here.
-- ------------------------------------------------