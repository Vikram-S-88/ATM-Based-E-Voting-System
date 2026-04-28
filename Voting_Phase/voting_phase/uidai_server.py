import sys
import os
import logging
import json
import base64
import mysql.connector
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding

load_dotenv()

# ==========================================
# 1. LOGGING & CONFIGURATION
# ==========================================
# Standard Logging Setup
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
log_dir = os.path.join(parent_dir, 'logs')

if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logger = logging.getLogger('UIDAI_Server')
logger.setLevel(logging.INFO)

if logger.hasHandlers(): logger.handlers.clear()

# Console Handler (Cyan Color for distinction)
console_handler = logging.StreamHandler()
console_formatter = logging.Formatter('\033[96m[UIDAI GOVT]\033[0m %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

app = Flask(__name__)

# Database Config (Uses same schema as others)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME')
}

# ==========================================
# 2. KEY MANAGEMENT
# ==========================================
# Load Private Key to DECRYPT the payload from ATM
private_key = None
key_path = os.path.join(current_dir, "uidai_private.pem")

if os.path.exists(key_path):
    with open(key_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None
        )
    logger.info(f"✔ UIDAI Private Key Loaded.")
else:
    logger.critical(f"❌ CRITICAL: Missing 'uidai_private.pem'. Cannot decrypt biometrics.")
    sys.exit(1)

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def decrypt_payload(encrypted_b64):
    """
    Decrypts the Base64 RSA Encrypted Fingerprint ID.
    Returns: The raw ID string (e.g., "1")
    """
    try:
        cipher_text = base64.b64decode(encrypted_b64)
        plaintext = private_key.decrypt(
            cipher_text,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return plaintext.decode('utf-8')
    except Exception as e:
        logger.error(f"Decryption Failure: {e}")
        return None

# ==========================================
# 4. API ENDPOINTS
# ==========================================

@app.route('/api/verify_biometric', methods=['POST'])
def verify_biometric():
    """
    Endpoint called by BANK SERVER.
    Payload: { 
        'aadhar_number': '123456789012', 
        'encrypted_fingerprint': 'Base64String...' 
    }
    """
    data = request.json
    aadhar_num = data.get('aadhar_number')
    enc_finger_id = data.get('encrypted_fingerprint')

    if not aadhar_num or not enc_finger_id:
        return jsonify({"match": False, "error": "Missing Data"}), 400

    logger.info(f"Received Verification Request for Aadhar: ...{aadhar_num[-4:]}")

    # 1. DECRYPT the Fingerprint ID (This proves ATM encrypted it securely)
    # The ATM sends the ID it got from the sensor (e.g., "1", "2")
    decrypted_id = decrypt_payload(enc_finger_id)
    
    if decrypted_id is None:
        logger.warning("⛔ Authentication Failed: Unable to Decrypt Payload.")
        return jsonify({"match": False, "error": "Decryption Failed"}), 400

    logger.info(f"Decrypted Fingerprint ID: {decrypted_id}")

    # 2. VERIFY against Database Registry
    # logic: Does Aadhar User X actually own Fingerprint ID Y?
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = "SELECT fingerprint_id FROM biometric_registry WHERE aadhar_number = %s"
        cursor.execute(query, (aadhar_num,))
        record = cursor.fetchone()

        if not record:
            logger.warning("⛔ Failed: Aadhar Number not found in Biometric Registry.")
            return jsonify({"match": False, "error": "User Not Found in Registry"}), 404

        stored_id = str(record['fingerprint_id'])
        input_id = str(decrypted_id).strip()

        if stored_id == input_id:
            logger.info("✅ MATCH CONFIRMED. Identity Verified.")
            return jsonify({"match": True, "message": "Biometric Verified"})
        else:
            logger.warning(f"❌ MISMATCH. Expected ID: {stored_id}, Got: {input_id}")
            return jsonify({"match": False, "error": "Fingerprint Mismatch"}), 200

    except Exception as e:
        logger.error(f"Database Error: {e}")
        return jsonify({"match": False, "error": "Internal Server Error"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "UIDAI Server Online", "mode": "RSA-4096 Secure"}), 200

if __name__ == '__main__':
    # Run on Port 5004 (Distinct from Bank=5000, EC=5001, Voting=5002, ATM=5003)
    print("\n[SYSTEM] UIDAI Biometric Server Starting on Port 5004...")
    app.run(port=5004, debug=True)