-- ================================================
-- Graham McCabe
-- 08_users.sql
-- Defines system users for Panther Airs.
--
-- Tables:
--   Users  - Stores login credentials and role
--            for all system users (seeded here with hashed passwords)
--
-- ================================================

DROP TABLE IF EXISTS Users;

-- ------------------------------------------------
-- Users
-- Stores all registered system users.
-- ------------------------------------------------
CREATE TABLE Users (
    id          INTEGER         NOT NULL AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(50)     NOT NULL UNIQUE,
    password    VARCHAR(255)    NOT NULL,
    user_type   ENUM('Admin', 'Employee') NOT NULL
);

-- ------------------------------------------------
-- Seed Data: Users
-- Passwords are stored as PBKDF2-SHA256 hashes generated
-- by werkzeug.security.generate_password_hash().
-- Plaintext credentials (for reference only — never stored):
--   Admin user:    username=admin    password=Admin@PCA1
--   Employee user: username=employee password=Employee@PCA1
-- ------------------------------------------------
INSERT IGNORE INTO Users (username, password, user_type) VALUES
    ('admin',
     'pbkdf2:sha256:1000000$JYPFEv4VIVrhxRrc$7e25ebff21026e084c292cde63ce80b0854d48ae4e84ccecf962991e62da467b',
     'Admin'),
    ('employee',
     'pbkdf2:sha256:1000000$ssJodReVsRHcUbf5$75f43bde27d4f25036d2f052a5fa77a1ea134a1c9af87422882990301038fa1f',
     'Employee');