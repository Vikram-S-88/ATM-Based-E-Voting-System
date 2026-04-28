import os
import sys
import time
import json
import base64
import serial
import atexit
import requests
import qrcode
import io
from functools import wraps
from flask import Flask, render_template, request, session, redirect, url_for, make_response, flash
from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding

load_dotenv()

# ==========================================
# 1. SERVER CONFIGURATION
# ==========================================
app = Flask(__name__)
# [SECURITY] Essential for Flash Messages
app.secret_key = os.getenv('ATM_SECRET_KEY', 'dev_key_fallback_please_change')

# Voting Server (Step 3 & Voting)
VOTING_SERVER_URL = "http://localhost:5002"
# Bank Server (Step 1 & 2 - PIN Check & Token Issue)
BANK_SERVER_URL = "http://localhost:5000"

# ==========================================
# 2. CRYPTOGRAPHY SETUP
# ==========================================
base_dir = os.path.dirname(os.path.abspath(__file__))

# A. Election Key (For Encrypting the Vote Choice)
election_public_key = None
vote_key_path = os.path.join(base_dir, "votes_public.pem")

if os.path.exists(vote_key_path):
    with open(vote_key_path, "rb") as f:
        election_public_key = serialization.load_pem_public_key(f.read())
    print(f"[SYSTEM] Loaded Election Public Key.")
else:
    print(f"[CRITICAL] Missing Election Key: {vote_key_path}")

# B. UIDAI Key (For Encrypting the Fingerprint ID)
uidai_public_key = None
uidai_key_path = os.path.join(base_dir, "uidai_public.pem")

if os.path.exists(uidai_key_path):
    with open(uidai_key_path, "rb") as f:
        uidai_public_key = serialization.load_pem_public_key(f.read())
    print(f"[SYSTEM] Loaded UIDAI Public Key.")
else:
    print(f"[CRITICAL] Missing UIDAI Key: {uidai_key_path}")

# ==========================================
# 3. HARDWARE CONNECTION (Robust Loop)
# ==========================================
COM_PORT = 'COM7' 
BAUD_RATE = 9600
arduino = None

print(f"\n[SYSTEM] Initializing Hardware Interface on {COM_PORT}...")

for i in range(3):
    try:
        arduino = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)
        time.sleep(2) # Allow Arduino to reboot
        print(f"[SUCCESS] Hardware Online on {COM_PORT}")
        break
    except Exception as e:
        print(f"[ATTEMPT {i+1}/3] Connection Failed: {e}")
        time.sleep(1)

if arduino is None:
    print("[CRITICAL ERROR] HARDWARE FAILURE. System Offline.")

def close_serial():
    if arduino and arduino.is_open:
        arduino.close()

atexit.register(close_serial)

# ==========================================
# 4. HELPER FUNCTIONS
# ==========================================
def no_cache(view):
    """Prevents users from using the 'Back' button to vote again"""
    @wraps(view)
    def no_cache_view(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = "0"
        return response
    return no_cache_view

# ==========================================
# 5. VOTING LOGIC FLOW
# ==========================================

@app.route('/')
@no_cache
def home():
    """Step 1: Home Screen / Hardware Reset"""
    session.clear()
    if arduino: 
        try: arduino.reset_input_buffer()
        except: pass
    return render_template('atm_login.html')

@app.route('/scan_rfid', methods=['POST'])
@no_cache
def scan_rfid():
    """Action: Scans Card -> Redirects to PIN Screen"""
    if arduino is None: return render_template('atm_login.html', error="Hardware Disconnected")
    print("\n[STEP 1] Scanning Card...")
    
    try: arduino.reset_input_buffer()
    except: pass

    start_time = time.time()
    card_uid = None
    
    # 60s Timeout
    while (time.time() - start_time) < 60:
        if arduino.in_waiting > 0:
            try:
                line = arduino.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith("CARD:"):
                    card_uid = line.split(":")[1]
                    break
            except: continue
        time.sleep(0.1)

    if card_uid:
        session['card_number'] = card_uid
        print(f"[SUCCESS] Card Detected: {card_uid}")
        return render_template('atm_pin.html') 
    else:
        return render_template('atm_login.html', error="Scan Failed: No Card Detected.")

@app.route('/verify_pin_stage', methods=['POST'])
@no_cache
def verify_pin_stage():
    """Step 2: Verify PIN (Stage 1) -> Redirects to Biometric Screen"""
    pin = request.form.get('pin')
    card = session.get('card_number')
    
    if not card: 
        return redirect('/')
    
    session['temp_pin'] = pin 

    try:
        # Request verification from the Bank Server
        payload = {'card_number': card, 'pin': pin, 'fingerprint_id': None}
        resp = requests.post(f"{BANK_SERVER_URL}/api/atm_verify", json=payload)
        
        # 1. SUCCESS: Proceed to Biometrics
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "pin_valid":
                return render_template('atm_scan.html') 
        
        # 2. FAILURE: Extract the dynamic error (e.g., "Invalid PIN. 2 attempts remaining.")
        error_data = resp.json()
        err_msg = error_data.get('error', 'Authentication Failed')
        
        print(f"[FAIL] {err_msg}")
        
        # Render the login template with the real error message
        return render_template('atm_login.html', error=err_msg)

    except Exception as e:
        return render_template('atm_login.html', error="System Connectivity Error")
    
@app.route('/final_auth_bio', methods=['POST'])
@no_cache
def final_auth_bio():
    """Step 3: Scan Finger -> Encrypt -> Get Token -> Authenticate"""
    if arduino is None: return render_template('atm_login.html', error="Hardware Offline")
    
    card = session.get('card_number')
    pin = session.get('temp_pin')
    
    if not card or not pin: return redirect('/')

    print("\n[STEP 3] Scanning Fingerprint...")
    try: arduino.reset_input_buffer()
    except: pass
    
    start_time = time.time()
    raw_finger_id = None
    
    # 60s Timeout
    while (time.time() - start_time) < 60:
        if arduino.in_waiting > 0:
            try:
                line = arduino.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith("FINGER:"):
                    raw_finger_id = line.split(":")[1]
                    break
            except: continue
        time.sleep(0.1)

    if not raw_finger_id:
        return render_template('atm_scan.html', error="Scan Timeout. Try Again.")

    # --- ENCRYPTION LOGIC ---
    print(f"[AUTH] Finger ID Captured: {raw_finger_id}. Encrypting...")
    
    encrypted_blob = None
    if uidai_public_key:
        try:
            encrypted = uidai_public_key.encrypt(
                raw_finger_id.encode(),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()), 
                    algorithm=hashes.SHA256(), 
                    label=None
                )
            )
            encrypted_blob = base64.b64encode(encrypted).decode('utf-8')
        except Exception as e:
            print(f"Encryption Error: {e}")
            return render_template('atm_login.html', error="Security Module Failure")
    else:
        return render_template('atm_login.html', error="UIDAI Keys Missing")

    # --- BANK HANDSHAKE ---
    print(f"[AUTH] Contacting Bank for Secure Token...")
    try:
        bank_payload = {'card_number': card, 'pin': pin, 'fingerprint_id': encrypted_blob}
        bank_resp = requests.post(f"{BANK_SERVER_URL}/api/atm_verify", json=bank_payload)
        
        if bank_resp.status_code != 200:
            err_msg = bank_resp.json().get('error', 'Biometric Check Failed')
            return render_template('atm_login.html', error=f"Auth Failed: {err_msg}")

        jwt_token = bank_resp.json().get('auth_token')
        
        # --- VOTING SERVER HANDSHAKE ---
        print(f"[AUTH] Accessing Voting System...")
        voting_payload = {'auth_token': jwt_token}
        vote_resp = requests.post(f"{VOTING_SERVER_URL}/api/authenticate", json=voting_payload)

        if vote_resp.status_code == 200:
            data = vote_resp.json()
            session['voter_alias'] = data.get('voter_alias')
            session['constituency'] = data.get('constituency_id', 1)
            session['candidates'] = data.get('candidates', []) # Empty list fallback
            
            session.pop('temp_pin', None)
            
            return redirect(url_for('ballot'))
        else:
            err = vote_resp.json().get('error', 'Voting Auth Failed')
            return render_template('atm_login.html', error=f"Access Denied: {err}")

    except Exception as e:
        print(f"[ERROR] Network Failure: {e}")
        return render_template('atm_login.html', error="System Connectivity Error")

@app.route('/ballot')
@no_cache
def ballot():
    if 'voter_alias' not in session: return redirect('/')
    
    # Pass Enumerated Candidates for Display
    candidates_list = session.get('candidates', [])
    candidates_enum = enumerate(candidates_list, 1)
    
    return render_template('atm_ballot.html', candidates_enum=candidates_enum)

@app.route('/submit_vote', methods=['POST'])
@no_cache
def submit_vote():
    """Step 4: Validate, Encrypt NUMBER, Submit"""
    if 'voter_alias' not in session: return redirect('/')
    
    choice = request.form.get('party_number', '').strip()
    candidates = session.get('candidates', [])
    
    # --- [UPDATED] VALIDATION LOGIC ---
    
    # Case 1: Timeout (Input is "0") -> ALLOW IT
    if choice == "0":
        print("[VOTE] Timeout detected. Invalid vote.")
    
    # Case 2: Manual Input Check
    else:
        try:
            idx = int(choice)
            # Strict Range Check
            if idx < 1 or idx > len(candidates):
                flash(f"Invalid Option: Please enter a number.")
                return redirect(url_for('ballot'))
        except ValueError:
            flash("Invalid Input: Please enter a numeric value.")
            return redirect(url_for('ballot'))
    
    # --- ENCRYPTION & SUBMISSION ---
    voter_hash = session['voter_alias']
    enc_vote = choice # String "0" or "1", "2"...
    
    if election_public_key:
        try:
            encrypted = election_public_key.encrypt(
                choice.encode(),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()), 
                    algorithm=hashes.SHA256(), 
                    label=None
                )
            )
            enc_vote = base64.b64encode(encrypted).decode('utf-8')
        except:
             return render_template('atm_login.html', error="Encryption Error")

    payload = {
        "voter_alias": voter_hash,
        "encrypted_vote": enc_vote,
        "constituency": session.get('constituency', 1)
    }
    
    try:
        requests.post(f"{VOTING_SERVER_URL}/api/vote", json=payload)
        print(f"[VOTE] Vote '{choice}' successfully queued.")
    except Exception as e:
        print(f"[ERROR] Blockchain submission failed: {e}")
    
    # --- GENERATE QR FOR RECEIPT ---
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(voter_hash)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    qr_b64 = base64.b64encode(buf.getvalue()).decode('ascii')

    session.clear()
    return render_template('atm_receipt.html', qr_code=qr_b64, hash_val=voter_hash)

if __name__ == '__main__':
    # Use reloader=False to prevent serial port conflict
    app.run(port=5003, debug=True, use_reloader=False)