/**
 * FINAL ATM FIRMWARE - DUAL SENSOR
 * Target: Arduino Uno
 * * Function: 
 * 1. Listens for RFID Card -> Sends "CARD:XXXXXXXX"
 * 2. Listens for Fingerprint -> Sends "FINGER:ID"
 */

#include <SPI.h>
#include <MFRC522.h>
#include <SoftwareSerial.h>
#include <Adafruit_Fingerprint.h>

// --- PIN CONFIGURATION ---
// RFID (SPI Protocol)
#define SS_PIN 10
#define RST_PIN 9

// Fingerprint (Software Serial)
// Pin 2 is acting as RX (Receive from Sensor Green wire)
// Pin 3 is acting as TX (Send to Sensor White wire)
SoftwareSerial mySerial(2, 3);

// --- OBJECTS ---
MFRC522 mfrc522(SS_PIN, RST_PIN);
Adafruit_Fingerprint finger = Adafruit_Fingerprint(&mySerial);

void setup() {
  // 1. Start Serial for Python Communication
  Serial.begin(9600);
  while (!Serial); // Wait for USB connection
  
  // 2. Start RFID (SPI)
  SPI.begin();
  mfrc522.PCD_Init();

  // 3. Start Fingerprint Sensor
  // Note: Most sensors default to 57600 baud
  finger.begin(57600); 
  
  // 4. Quick Hardware Check (Optional Debugging)
  if (finger.verifyPassword()) {
    // Fingerprint Sensor Detected
  } else {
    Serial.println("HARDWARE_ERROR: Fingerprint sensor not found. Check wiring!");
  }
}

void loop() {
  // Run checks sequentially
  checkRFID();
  checkFingerprint();
  
  // Short delay to prevent CPU overheating and serial flooding
  delay(50); 
}

// ==========================================
// 1. RFID LOGIC
// ==========================================
void checkRFID() {
  // Check if a new card is present
  if (!mfrc522.PICC_IsNewCardPresent()) {
    return;
  }
  
  // Verify if we can read the card serial
  if (!mfrc522.PICC_ReadCardSerial()) {
    return;
  }

  // Convert UID bytes to Hex String
  String tagID = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    // [CRITICAL] Add leading zero for single digit hex (e.g., 0xA -> "0A")
    if (mfrc522.uid.uidByte[i] < 0x10) {
      tagID += "0";
    }
    tagID += String(mfrc522.uid.uidByte[i], HEX);
  }
  tagID.toUpperCase(); // Ensure "ABC" not "abc"

  // [OUTPUT] Send to Python
  Serial.print("CARD:");
  Serial.println(tagID);

  // [IMPORTANT] Halt the card to stop reading it 100 times/sec
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  
  // Add a small delay so the user has time to remove the card
  delay(1000); 
}

// ==========================================
// 2. FINGERPRINT LOGIC
// ==========================================
void checkFingerprint() {
  // 1. Ask sensor to take an image
  uint8_t p = finger.getImage();
  
  // If no finger is there, exit immediately (Non-blocking)
  if (p == FINGERPRINT_NOFINGER) return;
  if (p != FINGERPRINT_OK) return; // Any other error

  // 2. Convert image to feature template
  p = finger.image2Tz();
  if (p != FINGERPRINT_OK) return;

  // 3. Search the database for a match
  p = finger.fingerFastSearch();
  
  if (p == FINGERPRINT_OK) {
    // [OUTPUT] Match Found! Send ID to Python
    Serial.print("FINGER:");
    Serial.println(finger.fingerID);
    
    // Delay to prevent multiple reads of the same press
    delay(1000); 
  }
  // Note: We do NOT print "Access Denied" here because the Python script 
  // only cares about valid scans. Printing errors might confuse the parser.
}
