import sys
import os
import logging
import datetime
import hashlib
import json
import requests
import mysql.connector
import random
import qrcode  # [NEW] For QR Generation
import base64  # [NEW] For Image Encoding
from dotenv import load_dotenv
from io import BytesIO
from flask import Flask, request, jsonify, render_template, session, send_file, redirect
from captcha.image import ImageCaptcha

load_dotenv()

# ==========================================
# 1. ROBUST LOGGING SETUP
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
log_dir = os.path.join(parent_dir, 'logs')

if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file_path = os.path.join(log_dir, 'transaction.log')

# Configure Logger
logger = logging.getLogger('ECServer')
logger.setLevel(logging.INFO)

if logger.hasHandlers():
    logger.handlers.clear()

file_handler = logging.FileHandler(log_file_path)
file_formatter = logging.Formatter('%(asctime)s - [EC GOVT] - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

console_handler = logging.StreamHandler()
console_formatter = logging.Formatter('\033[92m[EC PROTOCOL]\033[0m %(message)s') # Green Color
console_handler.setFormatter(console_formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


# ==========================================
# 2. SERVER CONFIGURATION
# ==========================================
app = Flask(__name__)
app.secret_key = os.getenv('EC_SECRET_KEY')

# RAM Cache for temporary Handshake Data
SESSION_CACHE = {} 

DB_CONFIG = {
    'host': os.getenv('DB_HOST'), 
    'user': os.getenv('DB_USER'), 
    'password': os.getenv('DB_PASSWORD'), 
    'database': os.getenv('DB_NAME')
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def generate_captcha_text(length=5):
    """Generates an Uppercase Alphanumeric CAPTCHA"""
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choice(chars) for _ in range(length))

def normalize_text(text):
    """
    STRICT NORMALIZATION:
    1. Lowercase
    2. Strip leading/trailing whitespace
    3. Remove multiple internal spaces (e.g. 'Arun  Kumar' -> 'arun kumar')
    """
    if not text: return ""
    return " ".join(str(text).lower().split())

def render_error_and_stop(token, cache, msg):
    """Updates attempts and returns the error page."""
    cache['attempts'] += 1
    remaining = 3 - cache['attempts']
    logger.warning(f"BLOCKED: {msg} (Attempts: {cache['attempts']}/3)")
    
    if remaining <= 0:
        if token in SESSION_CACHE: del SESSION_CACHE[token]
        return "<h3>Maximum attempts exceeded. Session Revoked.</h3>", 403
    
    return render_template('verify.html', token=token, error=f"{msg} ({remaining} attempts left)")


# ==========================================
# 3. ROUTES
# ==========================================

@app.route('/captcha_image')
def captcha_image():
    """Generates a CAPTCHA image for EC verification."""
    image = ImageCaptcha(width=280, height=90)
    captcha_text = generate_captcha_text()
    session['captcha_ans'] = captcha_text  # Store answer in session
    
    data = image.generate(captcha_text)
    return send_file(data, mimetype='image/png')

@app.route('/cancel')
def cancel_process():
    """Aborts the registration process safely."""
    token = session.get('current_token')
    
    # 1. Clean up server memory
    if token and token in SESSION_CACHE:
        del SESSION_CACHE[token]
        logger.info(f"Session {token} CANCELLED by user.")
    
    # 2. Clear browser session and redirect to Bank Home
    session.clear()
    return redirect("http://localhost:5000/")

@app.route('/api/initiate_session', methods=['POST'])
def initiate_session():
    """
    Secure Handshake Endpoint.
    Receives KYC data from Bank and issues a Session Token.
    """
    data = request.json
    logger.info(f"Incoming Connection from BANK. Payload received.")
    
    token = "SESS_" + hashlib.md5(str(datetime.datetime.now()).encode()).hexdigest()[:8]
    
    # Store KYC data in RAM to verify against Voter Roll later
    SESSION_CACHE[token] = { 
        'kyc': data, 
        'attempts': 0, 
        'created_at': datetime.datetime.now() 
    }
    
    logger.info(f"Session Created. Token Issued: {token}")
    return jsonify({"session_token": token})

@app.route('/verify', methods=['POST'])
def verify_page():
    """The landing page for the User arriving from the Bank."""
    token = request.form.get('session_token') or session.get('current_token')
    
    if not token or token not in SESSION_CACHE:
        logger.warning(f"Access Denied: Invalid Token {token}")
        return "Session Expired or Invalid", 403
        
    session['current_token'] = token
    logger.info(f"User entered Secure Tunnel. Token: {token}")
    return render_template('verify.html', token=token)

@app.route('/process_registration', methods=['POST'])
def process_registration():
    """
    CORE LOGIC:
    1. Validates Session & CAPTCHA
    2. Checks Government DB for Voter ID
    3. Compares Bank KYC vs Govt Data (Name, Father, DOB, Gender)
    4. Calls Bank API to get Blind Hash
    5. Saves Anonymous Hash to Token Pool
    """
    # --- 1. SESSION VALIDATION ---
    token = session.get('current_token')
    if not token or token not in SESSION_CACHE:
        return "Session Timed Out - Please Restart", 403
        
    cache = SESSION_CACHE[token]
    
    if cache['attempts'] >= 3:
        logger.error(f"Session {token} Revoked - Max Failures.")
        del SESSION_CACHE[token]
        return "<h3>Maximum attempts exceeded. Session Revoked.</h3>", 403

    # --- 2. CAPTCHA CHECK ---
    # [UPDATED] Added .upper() to ensure case-insensitivity
    user_captcha = request.form.get('captcha', '').strip()
    #user_captcha = request.form.get('captcha', '').strip().upper()
    correct_answer = session.get('captcha_ans')

    if not correct_answer or user_captcha != correct_answer:
        return render_error_and_stop(token, cache, "Incorrect CAPTCHA Code")

    # --- 3. INPUT SANITIZATION --- 
    #epic_id = request.form['epic_id'].strip()
    epic_id = request.form['epic_id'].strip().upper()

    # --- 4. DATABASE LOOKUP (GOVT DB) ---
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM voter_roll WHERE epic_id=%s", (epic_id,))
    voter = cursor.fetchone()
    
    if not voter:
        conn.close()
        return render_error_and_stop(token, cache, "Voter ID not found in Govt DB")

    # --- 5. LOGIC GATES (IDENTITY MATCHING) ---
    # Compare Bank Data (KYC) vs Govt Data (Voter Roll)
    bank_data = cache['kyc']
    logger.info(f"Verifying Identity for EPIC: {epic_id}")
    
    mismatches = []
    
    # Gate 1: Gender
    if bank_data['gender'] != voter['gender']: 
        mismatches.append(f"Gender ({bank_data['gender']} != {voter['gender']})")
    
    # Gate 2: DOB
    if str(bank_data['dob']) != str(voter['dob']):
        mismatches.append(f"DOB ({bank_data['dob']} != {voter['dob']})")
    
    # Gate 3: Name (Strict Normalization)
    norm_bank_name = normalize_text(bank_data['name'])
    norm_voter_name = normalize_text(voter['first_name'])
    
    if norm_bank_name != norm_voter_name:
        mismatches.append(f"Name Mismatch ('{norm_bank_name}' vs '{norm_voter_name}')")

    # Gate 4: Father's Name Verification
    bank_father = normalize_text(bank_data.get('father_name', ''))
    voter_father = normalize_text(voter.get('father_name', ''))

    if bank_father != voter_father:
        mismatches.append(f"Father Name Mismatch ('{bank_father}' vs '{voter_father}')")

    if mismatches:
        conn.close()
        logger.warning(f"Identity Verification Failed: {mismatches}")
        return render_error_and_stop(token, cache, "Identity Details (Name/Father/DOB) do not match Bank Records.")

    # --- 6. UNIQUENESS CHECK (Decoupled) ---
    # Check the Audit Log to see if this EPIC ID has already registered.
    cursor.execute("SELECT 1 FROM registration_audit WHERE epic_id=%s", (epic_id,))
    if cursor.fetchone():
        conn.close()
        return render_template('verify.html', token=token, error="Error: This Voter ID is ALREADY registered.")

    # --- 7. BANK HASHING (Double Blind) ---
    try:
        logger.info("Requesting Blind Hash from Bank...")
        # API Call back to Bank Server
        bank_response = requests.post('http://localhost:5000/api/generate_hash', json={'session_token': token}) 
        
        if bank_response.status_code != 200:
             conn.close()
             return "Bank Refused Transaction (Token Invalid)", 500
        bank_hash = bank_response.json()['bank_hash']
    except Exception as e:
        conn.close()
        logger.error(f"Bank Communication Error: {e}")
        return "Communication Error with Bank Server", 500

    # --- 8. FINAL COMMIT (Decoupled Architecture) ---
    govt_salt = os.getenv('GOVT_TOP_SECRET_SALT')
    # Final Hash = SHA256( BankHash + GovtSalt )
    final_hash = hashlib.sha256((bank_hash + govt_salt).encode()).hexdigest()
    
    try:
        # Step A: Insert into Audit Log (Records THAT they registered)
        cursor.execute("INSERT INTO registration_audit (epic_id) VALUES (%s)", (epic_id,))
        
        # Step B: Insert into Token Pool (Records THE PERMISSION to vote)
        # Note: Mathematically unlinked from Step A. This allows them to vote anonymously later.
        cursor.execute("INSERT INTO token_pool (final_hash, constituency_id) VALUES (%s, %s)",
                       (final_hash, voter['constituency_id']))

        conn.commit()
        logger.info(f"SUCCESS! New Voter Added to Pool. Hash: {final_hash}")
        
    except mysql.connector.Error as err:
        conn.rollback() 
        logger.error(f"DB Error: {err}")
        return f"Database Error during Registration: {err}", 500
    finally:
        conn.close()

    if token in SESSION_CACHE: del SESSION_CACHE[token] # Cleanup

    # --- [NEW] QR CODE GENERATION LOGIC ---
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(final_hash)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf)
        buf.seek(0)
        qr_b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception as e:
        logger.error(f"QR Code Generation Failed: {e}")
        qr_b64 = None  # Graceful fallback

    # Pass 'final_hash' (not 'hash') to match the new success.html
    return render_template('success.html', final_hash=final_hash, qr_code=qr_b64)

if __name__ == '__main__':
    print("\n[SYSTEM] EC Server Starting on Port 5001...")
    app.run(port=5001, debug=True)