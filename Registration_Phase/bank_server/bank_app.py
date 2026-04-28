import sys
import os
import logging
import random
import hashlib
import json
import time
import requests
import mysql.connector
import jwt  
from dotenv import load_dotenv
from io import BytesIO
from flask import Flask, render_template, request, session, redirect, jsonify, send_file, url_for
from captcha.image import ImageCaptcha
from twilio.rest import Client
from cryptography.hazmat.primitives import serialization

load_dotenv()

# ==========================================
# 1. LOGGING SETUP
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__)) 
parent_dir = os.path.dirname(current_dir)                
log_dir = os.path.join(parent_dir, 'logs')

if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file_path = os.path.join(log_dir, 'transaction.log')

# Configure Logger
logger = logging.getLogger('BankServer')
logger.setLevel(logging.INFO)

if logger.hasHandlers():
    logger.handlers.clear()

file_handler = logging.FileHandler(log_file_path)
file_formatter = logging.Formatter('%(asctime)s - [BANK] - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

console_handler = logging.StreamHandler()
# Removed ANSI colors and special chars for Windows compatibility
console_formatter = logging.Formatter('[BANK PROTOCOL] %(message)s')
console_handler.setFormatter(console_formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# ==========================================
# 2. SERVER & TWILIO CONFIGURATION
# ==========================================
app = Flask(__name__)
app.secret_key = os.getenv('BANK_SECRET_KEY') 

# --- TWILIO CREDENTIALS ---
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
POC_MOBILE_NUMBER = os.getenv('POC_MOBILE_NUMBER')    
UIDAI_SERVER_URL = "http://localhost:5004"

# Global Memory (RAM)
GLOBAL_USER_LOCKS = {}  
BANK_TOKEN_STORE = {}   

# Database Connection Config
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'), 
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'), 
    'database': os.getenv('DB_NAME')
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def generate_captcha_text(length=5):
    """Generates an Uppercase Alphanumeric String"""
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choice(chars) for _ in range(length))

# --- LOAD BANK PRIVATE KEY (For Signing JWTs) ---
bank_private_key = None
key_path = os.path.join(current_dir, "bank_private.pem")
if os.path.exists(key_path):
    with open(key_path, "rb") as f:
        bank_private_key = serialization.load_pem_private_key(f.read(), password=None)
    logger.info("[OK] Bank Private Key Loaded (RSA).")
else:
    logger.warning("[WARNING] 'bank_private.pem' NOT FOUND. Copy 'uidai_private.pem' and rename it to 'bank_private.pem' for the demo.")

# --- SMS HELPER FUNCTION ---
def send_sms_via_twilio(to_number, otp_code):
    print("\n" + "="*50)
    print(f"  [SMS GATEWAY] GENERATED OTP: {otp_code}")
    print(f"  Attempting to send SMS to: {to_number}")
    print("="*50 + "\n")

    try:
        formatted_number = str(to_number).strip()
        if not formatted_number.startswith("+"):
            formatted_number = "+91" + formatted_number 

        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        message = client.messages.create(
            body=f"Your Secure Bank OTP is: {otp_code}. Do not share this with anyone.",
            from_=TWILIO_PHONE_NUMBER,
            to=formatted_number
        )
        logger.info(f"SMS Sent to {formatted_number} | SID: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"SMS Failed: {e}")
        return False

# ==========================================
# 3. WEB ROUTES (Login & OTP)
# ==========================================
@app.route('/captcha_image')
def captcha_image():
    image = ImageCaptcha(width=280, height=90)
    captcha_text = generate_captcha_text()
    session['login_captcha'] = captcha_text
    data = image.generate(captcha_text)
    return send_file(data, mimetype='image/png')

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/authenticate', methods=['POST'])
def authenticate():
    username = request.form['username']
    password = request.form['password'] 
    
    # Case-insensitive captcha check
    user_captcha = request.form.get('captcha', '')
    #user_captcha = request.form.get('captcha', '').upper()
    
    correct_captcha = session.get('login_captcha')
    
    if not correct_captcha or user_captcha != correct_captcha:
        return render_template('login.html', error="Invalid CAPTCHA Code")

    user_lock = GLOBAL_USER_LOCKS.get(username, {'attempts': 0, 'locked_until': 0})
    if time.time() < user_lock['locked_until']:
        remaining = int(user_lock['locked_until'] - time.time())
        return render_template('login.html', error=f"Account Locked! Try again in {remaining}s.")

    logger.info(f"Auth Request for user: {username}")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM bank_customers WHERE username=%s AND password=%s", (username, password))
    user = cursor.fetchone()
    conn.close()

    if user:
        GLOBAL_USER_LOCKS[username] = {'attempts': 0, 'locked_until': 0}
        session['user_cif'] = user['cif_id']
        session['username'] = username
        session['mobile_no'] = user['mobile']
        session['kyc_data'] = {
            'name': user['kyc_name'],
            'father_name': user['father_name'], 
            'gender': user['kyc_gender'],
            'dob': str(user['kyc_dob'])
        }
        otp = str(random.randint(100000, 999999))
        session['generated_otp'] = otp
        session['otp_attempts'] = 0            
        session['last_otp_time'] = time.time() 
        logger.info(f"Login Success for {username}.")
        send_sms_via_twilio(POC_MOBILE_NUMBER, otp)
        return render_template('consent.html', mobile_last_4=user['mobile'][-4:], error=None)
    else:
        user_lock['attempts'] += 1
        if user_lock['attempts'] >= 3:
            user_lock['locked_until'] = time.time() + 60 
            GLOBAL_USER_LOCKS[username] = user_lock
            return render_template('login.html', error="Too many failed attempts. Account Locked for 60s.")
        GLOBAL_USER_LOCKS[username] = user_lock
        logger.warning(f"Failed Login: {username}")
        remaining = 3 - user_lock['attempts']
        return render_template('login.html', error=f"Invalid Credentials. {remaining} attempts left.")
    
@app.route('/resend_otp', methods=['POST'])
def resend_otp():
    if 'user_cif' not in session:
        return jsonify({"message": "Session Expired"}), 403
    
    last_sent = session.get('last_otp_time', 0)
    time_diff = time.time() - last_sent
    if time_diff < 30:
        wait_time = int(30 - time_diff)
        return jsonify({"message": f"Please wait {wait_time} seconds before resending."}), 429
    
    new_otp = str(random.randint(100000, 999999))
    session['generated_otp'] = new_otp
    session['last_otp_time'] = time.time() 
    session['otp_attempts'] = 0            
    logger.info(f"OTP Resend Triggered.")
    send_sms_via_twilio(POC_MOBILE_NUMBER, new_otp)
    return jsonify({"status": "sent", "message": "OTP Resent Successfully via SMS"})

@app.route('/verify_otp_consent', methods=['POST'])
def verify_otp_consent():
    user_otp = request.form['otp']
    consent = request.form.get('consent')
    username = session.get('username')

    if not username: return redirect('/')

    attempts = session.get('otp_attempts', 0)
    if attempts >= 3:
        session.clear()
        return render_template('login.html', error="Max OTP attempts exceeded. Please login again.")

    if user_otp == session.get('generated_otp'):
        logger.info("OTP Verified Successfully.")
        if not consent:
             return render_template('consent.html', mobile_last_4=session['mobile_no'][-4:], error="You must agree to consent.")
        kyc_payload = session['kyc_data']
        try:
            logger.info(">>> INITIATING SECURE HANDSHAKE WITH EC <<<")
            response = requests.post('http://localhost:5001/api/initiate_session', json=kyc_payload)
            if response.status_code == 200:
                ec_token = response.json()['session_token']
                BANK_TOKEN_STORE[ec_token] = session['user_cif']
                return render_template('redirect.html', token=ec_token, ec_url='http://localhost:5001/verify')
            else:
                return f"EC Server Error: {response.text}", 500
        except Exception as e:
            return "Error: EC Server is down or unreachable.", 500
    else:
        session['otp_attempts'] = attempts + 1
        remaining = 3 - session['otp_attempts']
        logger.warning(f"Invalid OTP. Attempts left: {remaining}")
        if remaining <= 0:
            session.clear()
            return render_template('login.html', error="Max OTP attempts exceeded. Account Locked.")
        return render_template('consent.html', mobile_last_4=session['mobile_no'][-4:], error=f"Invalid OTP. {remaining} attempts remaining.")

@app.route('/api/generate_hash', methods=['POST'])
def generate_hash():
    data = request.json
    received_token = data.get('session_token')
    if received_token not in BANK_TOKEN_STORE:
        return jsonify({"error": "Invalid Token"}), 403
    cif_id = BANK_TOKEN_STORE[received_token]
    bank_salt = "BANK_PRIVATE_SALT_XYZ"
    bank_hash = hashlib.sha256(f"{cif_id}{bank_salt}".encode()).hexdigest()
    del BANK_TOKEN_STORE[received_token]
    return jsonify({"bank_hash": bank_hash}), 200

# ==========================================
# ATM VERIFICATION (Federated w/ UIDAI)
# ==========================================
@app.route('/api/atm_verify', methods=['POST'])
def atm_verify():
    from datetime import datetime, timedelta
    data = request.json
    
    input_hex_code = data.get('card_number') 
    input_pin = data.get('pin')  
    fp_blob_encrypted = data.get('fingerprint_id') 

    # Standard logging for the ATM request
    print(f"\n[DEBUG] ATM Request: RFID={input_hex_code} | PIN={input_pin} | FP_Present={bool(fp_blob_encrypted)}")
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 1. FETCH CARD AND CHECK LOCK STATUS
        # This checks the card_mapper table for persistent failed_attempts and locked_until
        query_map = "SELECT card_number, failed_attempts, locked_until FROM card_mapper WHERE rfid_hex_code = %s AND is_active = TRUE"
        cursor.execute(query_map, (input_hex_code,))
        mapping = cursor.fetchone()

        if not mapping:
            return jsonify({"error": "Card Not Recognized"}), 404

        # Check if the user is currently in a 1-minute lockout
        if mapping['locked_until'] and mapping['locked_until'] > datetime.now():
            remaining = int((mapping['locked_until'] - datetime.now()).total_seconds())
            return jsonify({"error": f"Security Block: Try again in {remaining}s"}), 403

        # 2. VERIFY PIN (STAGE 1)
        real_card_number = mapping['card_number']
        query_bank = "SELECT cif_id, aadhar_number FROM bank_customers WHERE card_number = %s AND atm_pin = %s"
        cursor.execute(query_bank, (real_card_number, input_pin))
        bank_user = cursor.fetchone()

        # Handle PIN Failure: Increment failure counter persistently
        if not bank_user:
            new_attempts = mapping['failed_attempts'] + 1
            if new_attempts >= 3:
                lock_time = datetime.now() + timedelta(minutes=1)
                cursor.execute("UPDATE card_mapper SET failed_attempts=3, locked_until=%s WHERE rfid_hex_code=%s", 
                             (lock_time, input_hex_code))
                error_msg = "Max attempts reached. Card blocked for 60s."
            else:
                cursor.execute("UPDATE card_mapper SET failed_attempts=%s WHERE rfid_hex_code=%s", 
                             (new_attempts, input_hex_code))
                error_msg = f"Invalid PIN {3 - new_attempts} attempts remaining."
            
            conn.commit()
            return jsonify({"error": error_msg}), 503

        # PIN is correct, but we only issue the token after successful biometric scan
        if not fp_blob_encrypted:
            return jsonify({
                "status": "pin_valid", 
                "message": "PIN Accepted. Please Scan Fingerprint."
            })

        # 3. VERIFY BIOMETRIC (STAGE 2)
        user_aadhar = bank_user['aadhar_number']
        try:
            uidai_payload = {'aadhar_number': user_aadhar, 'encrypted_fingerprint': fp_blob_encrypted}
            uidai_resp = requests.post(f"{UIDAI_SERVER_URL}/api/verify_biometric", json=uidai_payload, timeout=5)
            uidai_data = uidai_resp.json()
            
            # Handle Biometric Failure: Also increments the same attempt counter
            if uidai_resp.status_code != 200 or not uidai_data.get('match'):
                new_attempts = mapping['failed_attempts'] + 1
                if new_attempts >= 3:
                    lock_time = datetime.now() + timedelta(minutes=1)
                    cursor.execute("UPDATE card_mapper SET failed_attempts=3, locked_until=%s WHERE rfid_hex_code=%s", 
                                 (lock_time, input_hex_code))
                    error_msg = "Max biometric attempts reached. Card blocked for 60s."
                else:
                    cursor.execute("UPDATE card_mapper SET failed_attempts=%s WHERE rfid_hex_code=%s", 
                                 (new_attempts, input_hex_code))
                    error_msg = f"Fingerprint Mismatch. {3 - new_attempts} attempts remaining."
                
                conn.commit()
                return jsonify({"error": error_msg}), 403
                
        except Exception as e:
            return jsonify({"error": "UIDAI Server Unreachable"}), 503

        # 4. SUCCESS: RESET COUNTERS AND ISSUE JWT
        # Resetting the counter only after both factors (PIN + Bio) pass
        cursor.execute("UPDATE card_mapper SET failed_attempts=0, locked_until=NULL WHERE rfid_hex_code=%s", 
                     (input_hex_code,))
        conn.commit()
        
        cif_id = bank_user['cif_id']
        bank_hash = hashlib.sha256(f"{cif_id}BANK_PRIVATE_SALT_XYZ".encode()).hexdigest()
        
        token_payload = {
            "bank_hash": bank_hash,
            "iss": "BANK_SERVER_01",
            "exp": time.time() + 300 
        }
        
        auth_token = jwt.encode(token_payload, bank_private_key, algorithm="RS256")
        return jsonify({"status": "valid", "auth_token": auth_token})

    except Exception as e:
        logger.error(f"System Error during ATM Verify: {e}")
        return jsonify({"error": "Bank Server Error"}), 500
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    print("[BANK] Server running on Port 5000...")
    app.run(port=5000, debug=True)