USE ec_voting_system;

-- 1. Constituencies
INSERT INTO constituencies (name) VALUES ('Chennai South');   -- ID: 1
INSERT INTO constituencies (name) VALUES ('Chengalpattu');    -- ID: 2
INSERT INTO constituencies (name) VALUES ('Tambaram');        -- ID: 3

-- 2. Candidates
INSERT INTO candidates (party_name) VALUES 
('Party A'), 
('Party B'), 
('Party C'), 
('Party D'), 
('NOTA');

-- 3. Voter Roll (Government Data)
-- Existing 4
INSERT INTO voter_roll VALUES 
('ABC1234567', 'Arun Kumar',   'Rajesh Kumar', 'M', '1995-05-15', 1),
('XYZ9876543', 'Priya S',      'Suresh S',     'F', '1998-08-20', 3),
('DEF1112223', 'Vikram Babu', 'Mohan Singh',  'F', '1992-01-10', 2),
('GHI3334445', 'Anjali Devi',  'Ravi Kumar',   'F', '2000-11-25', 1),
('VOT0000005', 'Ram P',     'Pandian K',    'M', '1990-01-01', 1), -- Chennai South
('VOT0000006', 'Suresh K',     'Kannan R',     'M', '1991-02-02', 1), -- Chennai South
('VOT0000007', 'Deepa M',      'Manohar L',    'F', '1993-03-03', 2), -- Chengalpattu
('VOT0000008', 'Karthik J',    'Jayaraman T',  'M', '1994-04-04', 2), -- Chengalpattu
('VOT0000009', 'Lakshmi S',    'Sundar P',     'F', '1995-05-05', 3), -- Tambaram
('VOT0000010', 'Meena R',      'Ramesh B',     'F', '1996-06-06', 3), -- Tambaram
('VOT0000011', 'Balaji V',     'Varun K',      'M', '1988-07-07', 1), -- Chennai South
('VOT0000012', 'Divya T',      'Thirumal R',   'F', '1999-08-08', 2), -- Chengalpattu
('VOT0000013', 'Ganesh G',     'Guna S',       'M', '1985-09-09', 3), -- Tambaram
('VOT0000014', 'Hema Malini',  'Krishnan',     'F', '1980-10-10', 1); -- Chennai South

-- 4. Bank Customers (Financial Data)
-- Linking CIF_005 to VOT0000005, etc.
INSERT INTO bank_customers VALUES 
('CIF_001', '1111222233334444', 'user1', 'pass1', '1111', '8825400475', 'Arun Kumar', 'Rajesh Kumar', 'M', '1995-05-15', '111122223333'),
('CIF_002', '5555666677778888', 'user2', 'pass2', '2222', '8825400475', 'Priya S', 'Suresh S', 'F', '1998-08-20', '555566667777'),
('CIF_003', '1234123412341234', 'user3', 'pass3', '3333', '7449053577', 'Vikram Babu', 'Mohan Singh', 'F', '1992-01-10', '123412341234'),
('CIF_004', '4321432143214321', 'user4', 'pass4', '4444', '7777777777', 'Anjali Devi', 'Ravi Kumar', 'F', '2000-11-25', '432143214321'),
-- New Users (Simplified Data for Simulation)
('CIF_005', '5000000000000005', 'user5',  'pass5',  '5555', '9000000005', 'Ram P', 'Pandian K', 'M', '1990-01-01', '223326267878'),
('CIF_006', '6000000000000006', 'user6',  'pass6',  '6666', '9000000006', 'Suresh K', 'Kannan R', 'M', '1991-02-02', '223326257878'),
('CIF_007', '7000000000000007', 'user7',  'pass7',  '7777', '9000000007', 'Deepa M', 'Manohar L', 'F', '1993-03-03', '223326247878'),
('CIF_008', '8000000000000008', 'user8',  'pass8',  '8888', '9000000008', 'Karthik J', 'Jayaraman T', 'M', '1994-04-04', '223126267878'),
('CIF_009', '9000000000000009', 'user9',  'pass9',  '9999', '9000000009', 'Lakshmi S', 'Sundar P', 'F', '1995-05-05', '223326167878'),
('CIF_010', '1000000000000010', 'user10', 'pass10', '1010', '9000000010', 'Meena R', 'Ramesh B', 'F', '1996-06-06', '223326262878'),
('CIF_011', '1100000000000011', 'user11', 'pass11', '1111', '9000000011', 'Balaji V', 'Varun K', 'M', '1988-07-07', '223326263878'),
('CIF_012', '1200000000000012', 'user12', 'pass12', '1212', '9000000012', 'Divya T', 'Thirumal R', 'F', '1999-08-08', '223326867878'),
('CIF_013', '1300000000000013', 'user13', 'pass13', '1313', '9000000013', 'Ganesh G', 'Guna S', 'M', '1985-09-09', '223326267978'),
('CIF_014', '1400000000000014', 'user14', 'pass14', '1414', '9000000014', 'Hema Malini', 'Krishnan', 'F', '1980-10-10', '223306267878');

-- 6. Biometric Registry (Mock Data - Fingerprint ID is just an integer here)
INSERT INTO biometric_registry VALUES
('111122223333', 1), ('555566667777', 2), ('123412341234', 3), ('432143214321', 4),
('223326267878', 5), ('223326257878', 6), ('223326247878', 7), ('223126267878', 8),
('223326167878', 9), ('223326262878', 10), ('223326263878', 11), ('223326867878', 12),
('223326267978', 13), ('223306267878', 14);


-- 5. Direct Mapping (EPIC -> Bank Card)
INSERT INTO epic_card_mapping (epic_id, card_number) VALUES
('ABC1234567', '1111222233334444'),
('XYZ9876543', '5555666677778888'),
('DEF1112223', '1234123412341234'),
('GHI3334445', '4321432143214321'),
('VOT0000005', '5000000000000005'),
('VOT0000006', '6000000000000006'),
('VOT0000007', '7000000000000007'),
('VOT0000008', '8000000000000008'),
('VOT0000009', '9000000000000009'),
('VOT0000010', '1000000000000010'),
('VOT0000011', '1100000000000011'),
('VOT0000012', '1200000000000012'),
('VOT0000013', '1300000000000013'),
('VOT0000014', '1400000000000014');

-- 7. Card Hardware Mapping (Updated for Security Lockout)
-- Values 5 and 6 are initialized to 0 and NULL to start fresh for each user 
INSERT INTO card_mapper (card_number, rfid_hex_code, cif_id, is_active, failed_attempts, locked_until) VALUES 
('1111222233334444', '3E8B90AE', 'CIF_001', TRUE, 0, NULL),
('5555666677778888', 'DE6D52A9', 'CIF_002', TRUE, 0, NULL),
('1234123412341234', '4EE99FB9', 'CIF_003', TRUE, 0, NULL),
('4321432143214321', '03C39FFA', 'CIF_004', TRUE, 0, NULL),
('5000000000000005', 'D171BB24', 'CIF_005', TRUE, 0, NULL),
('6000000000000006', 'xyz', 'CIF_006', TRUE, 0, NULL),
('7000000000000007', 'wxy', 'CIF_007', TRUE, 0, NULL),
('8000000000000008', 'pqr', 'CIF_008', TRUE, 0, NULL),
('9000000000000009', 'efg', 'CIF_009', TRUE, 0, NULL),
('1100000000000011', 'HEX_11', 'CIF_011', TRUE, 0, NULL),
('1200000000000012', 'HEX_12', 'CIF_012', TRUE, 0, NULL),
('1300000000000013', 'HEX_13', 'CIF_013', TRUE, 0, NULL),
('1400000000000014', 'HEX_14', 'CIF_014', TRUE, 0, NULL);