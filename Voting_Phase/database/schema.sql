DROP DATABASE IF EXISTS ec_voting_system;
CREATE DATABASE ec_voting_system;
USE ec_voting_system;

-- 1. Constituencies
CREATE TABLE constituencies (
    constituency_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

-- 2. Voter Roll
CREATE TABLE voter_roll (
    epic_id VARCHAR(20) PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    father_name VARCHAR(100),
    gender ENUM('M', 'F', 'O') NOT NULL,
    dob DATE NOT NULL,
    constituency_id INT UNSIGNED NOT NULL,
    FOREIGN KEY (constituency_id) REFERENCES constituencies(constituency_id)
);

-- 3. Registration Audit
CREATE TABLE registration_audit (
    audit_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    epic_id VARCHAR(20) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Token Pool
CREATE TABLE token_pool (
    final_hash CHAR(64) PRIMARY KEY,
    constituency_id INT UNSIGNED NOT NULL,
    has_voted BOOLEAN DEFAULT FALSE
);

-- 5. Bank Customers
CREATE TABLE bank_customers (
    cif_id VARCHAR(20) PRIMARY KEY,
    card_number VARCHAR(16) UNIQUE,
    username VARCHAR(50) UNIQUE,
    password VARCHAR(50),
    atm_pin VARCHAR(4),
    mobile VARCHAR(15),
    kyc_name VARCHAR(100),
    father_name VARCHAR(100),
    kyc_gender ENUM('M', 'F', 'O'),
    kyc_dob DATE,
    aadhar_number VARCHAR(12) UNIQUE NOT NULL
);

-- 6. Direct Mapping (EPIC <-> Card)
CREATE TABLE epic_card_mapping (
    mapping_id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    epic_id VARCHAR(20) NOT NULL,
    card_number VARCHAR(16) NOT NULL,
    FOREIGN KEY (epic_id) REFERENCES voter_roll(epic_id),
    FOREIGN KEY (card_number) REFERENCES bank_customers(card_number)
);

-- 7. Biometric Registry
CREATE TABLE biometric_registry (
    aadhar_number VARCHAR(12) PRIMARY KEY,
    fingerprint_id INT UNIQUE NOT NULL,
    FOREIGN KEY (aadhar_number) REFERENCES bank_customers(aadhar_number)
);

-- 8. Card Mapper (Enhanced with Security Lockout)
CREATE TABLE card_mapper(
    card_number VARCHAR(16) PRIMARY KEY,
    rfid_hex_code VARCHAR(20) UNIQUE NOT NULL,
    cif_id VARCHAR(20) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    failed_attempts INT DEFAULT 0,          -- Tracks consecutive PIN/Bio failures
    locked_until DATETIME DEFAULT NULL,      -- Stores the 1-minute block expiry time
    FOREIGN KEY (cif_id) REFERENCES bank_customers(cif_id)
);

-- 9. Candidates Table
CREATE TABLE candidates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    party_name VARCHAR(100) NOT NULL
);