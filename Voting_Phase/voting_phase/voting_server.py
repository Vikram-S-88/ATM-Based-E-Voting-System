import sys
import os
import hashlib
import json
import logging
import base64
import requests
import mysql.connector
import jwt  
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
from collections import defaultdict
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from blockchain import Blockchain  

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

logger = logging.getLogger('VotingServer')
logger.setLevel(logging.INFO)

if logger.hasHandlers(): logger.handlers.clear()

file_handler = logging.FileHandler(log_file_path)
file_formatter = logging.Formatter('%(asctime)s - [VOTING BACKEND] - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

console_handler = logging.StreamHandler()
console_formatter = logging.Formatter('\033[95m[ELECTION CORE]\033[0m %(message)s') 
console_handler.setFormatter(console_formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


# ==========================================
# 2. SERVER CONFIGURATION
# ==========================================
app = Flask(__name__)

# [SECURITY] CHECK FOR POA PRIVATE KEY
key_path = os.path.join(current_dir, "poa_private.pem")
if not os.path.exists(key_path):
    logger.critical("CRITICAL ERROR: 'poa_private.pem' NOT FOUND.")
    logger.critical("   The Voting Server is the Election Authority.")
    sys.exit(1) 

vote_chain = Blockchain() 
logger.info("✔ Authority Key Verified. Blockchain Initialized.")

# --- LOAD COUNTING KEY (Required for /api/results) ---
counting_key_path = os.path.join(current_dir, "votes_private.pem")
counting_private_key = None
if os.path.exists(counting_key_path):
    with open(counting_key_path, "rb") as f:
        counting_private_key = serialization.load_pem_private_key(f.read(), password=None)
    logger.info("✔ Counting Private Key Loaded (Results Mode Enabled).")
else:
    logger.warning("⚠ Missing 'votes_private.pem'. Results decryption will fail.")

# Configuration
BATCH_SIZE = 3
BANK_SERVER_URL = "http://localhost:5000"

# Database Config
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'), 
    'user': os.getenv('DB_USER', 'root'), 
    'password': os.getenv('DB_PASSWORD', 'selva'), 
    'database': os.getenv('DB_NAME', 'ec_voting_system')
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

# --- LOAD BANK PUBLIC KEY ---
bank_public_key = None
bank_key_path = os.path.join(current_dir, "bank_public.pem")

if os.path.exists(bank_key_path):
    with open(bank_key_path, "rb") as f:
        bank_public_key = serialization.load_pem_public_key(f.read())
    logger.info("✔ Bank Public Key Loaded.")
else:
    fallback_path = os.path.join(current_dir, "uidai_public.pem")
    if os.path.exists(fallback_path):
        with open(fallback_path, "rb") as f:
            bank_public_key = serialization.load_pem_public_key(f.read())
        logger.warning("⚠ USING UIDAI KEY AS BANK KEY (DEMO MODE)")

# ==========================================
# 3. CORE API ENDPOINTS
# ==========================================

@app.route('/api/authenticate', methods=['POST'])
def authenticate():
    """Called by ATM. Authenticates, Checks Integrity, Auto-Registers."""
    data = request.json
    token = data.get('auth_token')
    
    if not token or not bank_public_key:
        return jsonify({"error": "Auth Error"}), 400

    try:
        decoded_payload = jwt.decode(token, bank_public_key, algorithms=["RS256"])
        bank_hash = decoded_payload.get('bank_hash')
        if not bank_hash: return jsonify({"error": "Invalid Token"}), 400
        logger.info(f"✔ Token Verified. Bank Hash: {bank_hash[:10]}...")

    except Exception as e:
        logger.error(f"Token Error: {e}")
        return jsonify({"error": "Token Invalid"}), 401

    # Generate Anonymous ID
    govt_salt = os.getenv('GOVT_TOP_SECRET_SALT')
    final_hash = hashlib.sha256(f"{bank_hash}{govt_salt}".encode()).hexdigest()

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Integrity Check
        if vote_chain.voter_already_voted(final_hash):
            logger.critical(f"SECURITY ALERT: Replay detected for {final_hash[:8]}")
            cursor.execute("UPDATE token_pool set has_voted=1 where final_hash = %s", (final_hash,))
            conn.commit()
            return jsonify({"error": "Double Vote Detected"}), 409

        # Check Eligibility
        cursor.execute("SELECT has_voted, constituency_id FROM token_pool WHERE final_hash = %s", (final_hash,))
        user = cursor.fetchone()
        
        # [AUTO-REGISTRATION]
        # if not user:
        #     #return jsonify({"error": "Voter not registered"}), 409
            
        #     logger.info(f"New Voter Detected! Auto-Registering {final_hash[:8]}...")
        #     auto_constituency = (int(final_hash, 16) % 3) + 1 
            
        #     cursor.execute(
        #         "INSERT INTO token_pool (final_hash, constituency_id, has_voted) VALUES (%s, %s, 0)", 
        #         (final_hash, auto_constituency)
        #     )
        #     conn.commit()
        #     user = {'constituency_id': auto_constituency, 'has_voted': 0}
        #     logger.info(f"✔ Auto-Registered to Constituency ID: {auto_constituency}")

        if user['has_voted']: return jsonify({"error": "Already Voted"}), 409
            
        logger.info(f"Voter Authorized! Constituency ID: {user['constituency_id']}")

        # Fetch Candidates
        cursor.execute("SELECT party_name FROM candidates ORDER BY id ASC")
        rows = cursor.fetchall()
        candidate_list = [row['party_name'] for row in rows] if rows else ["Party A", "Party B", "NOTA"]

        return jsonify({
            "status": "success",
            "voter_alias": final_hash,
            "constituency_id": user['constituency_id'],
            "candidates": candidate_list 
        })

    except Exception as e:
        logger.error(f"Database Error: {e}")
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/api/vote', methods=['POST'])
def cast_vote():
    """Receives Encrypted Vote. Batches and Seals Blocks."""
    data = request.json
    alias = data.get('voter_alias')
    enc_vote = data.get('encrypted_vote')
    constituency = data.get('constituency')
    
    if vote_chain.voter_already_voted(alias):
        return jsonify({"status": "REJECTED", "error": "Duplicate Vote"}), 409

    result = vote_chain.add_vote(alias, enc_vote, constituency)
    if result == -1: return jsonify({"status": "REJECTED", "error": "Internal Error"}), 409
    
    logger.info(f"Vote Received from {alias[:10]}...")
    
    response_msg = "Vote Queued"
    tx_hash = "PENDING"
    final_block_index = -1 
    
    # Batch Sealing
    if len(vote_chain.pending_votes) >= BATCH_SIZE:
        logger.info(f"Batch Size Reached. Sealing Block...")
        block = vote_chain.create_block(validator_id=vote_chain.authority_id)
        
        if not block.get('signature'):
             logger.error("CRITICAL: Block creation returned UNSIGNED block.")
             return jsonify({"error": "Server Signing Failure"}), 500

        tx_hash = vote_chain.hash(block)
        final_block_index = block['index']
        response_msg = f"Block #{final_block_index} Sealed!"
    
    # Mark DB as voted
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE token_pool SET has_voted=1 WHERE final_hash=%s", (alias,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"DB Update Error: {e}")
    
    return jsonify({"status": response_msg, "tx_hash": tx_hash, "block_index": final_block_index})

# ==========================================
# 4. RESULTS & DASHBOARD (ENHANCED)
# ==========================================

@app.route('/counting')
def counting_dashboard():
    """Renders the Vote Counting UI"""
    if not counting_private_key:
        return "<h1>Error: Server missing Decryption Key (votes_private.pem)</h1>", 503
    return render_template('counting.html')

@app.route('/api/results')
def get_results():
    """
    Returns:
    - Global Total & Invalid Counts
    - Per-Constituency Total, Invalid, and Breakdown
    """
    if not counting_private_key:
        return jsonify({"error": "Server missing private key"}), 500

    # A. FETCH METADATA
    candidate_map = {}
    valid_ids = set()
    constituency_map = {} 
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, party_name FROM candidates ORDER BY id ASC")
        for idx, (db_id, name) in enumerate(cursor.fetchall(), 1):
            candidate_map[str(idx)] = name
            valid_ids.add(str(idx))
            
        cursor.execute("SELECT constituency_id, name FROM constituencies")
        for (c_id, c_name) in cursor.fetchall():
            constituency_map[str(c_id)] = c_name
        conn.close()
    except Exception as e:
        logger.error(f"DB Metadata Load Failed: {e}")
        return jsonify({"error": "Database Connectivity Failed"}), 500

    # B. INITIALIZE DATA
    constituency_results = {}
    for c_id, c_name in constituency_map.items():
        constituency_results[c_name] = {
            "total_votes": 0,
            "status": "Polling Not Started", 
            "breakdown": {name: 0 for name in candidate_map.values()},
            "winner": "N/A"
        }
        constituency_results[c_name]["breakdown"]["Invalid vote"] = 0

    global_tally = {name: 0 for name in candidate_map.values()}
    global_tally["Invalid vote"] = 0
    total_votes_casted = 0

    # C. LOAD & DECRYPT
    ledger_path = os.path.join(current_dir, "local_ledger.json")
    chain_data = vote_chain.chain
    if os.path.exists(ledger_path):
        try:
            with open(ledger_path, "r") as f: chain_data = json.load(f)
        except: pass

    # D. TALLY LOGIC
    for block in chain_data:
        for vote in block['votes']:
            try:
                # Decrypt
                cipher_text = base64.b64decode(vote['vote_data'])
                plaintext = counting_private_key.decrypt(
                    cipher_text,
                    padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
                ).decode('utf-8')
                
                party_num = plaintext.strip()
                c_id_raw = str(vote.get('constituency', 'Unknown'))
                c_name = constituency_map.get(c_id_raw, "Unknown Region")
                
                if c_name not in constituency_results:
                     constituency_results[c_name] = {"total_votes": 0, "status": "Active", "breakdown": defaultdict(int), "winner": "-"}

                constituency_results[c_name]["status"] = "Active"

                if party_num in valid_ids:
                    party_name = candidate_map[party_num]
                    global_tally[party_name] += 1
                    constituency_results[c_name]["breakdown"][party_name] += 1
                else:
                    global_tally["Invalid vote"] += 1
                    constituency_results[c_name]["breakdown"]["Invalid vote"] += 1
                
                constituency_results[c_name]["total_votes"] += 1
                total_votes_casted += 1

            except Exception as e:
                logger.error(f"Decryption Fail: {e}")

    # E. DETERMINE WINNERS
    for c_name, data in constituency_results.items():
        if data["status"] == "Active":
            tally = data["breakdown"]
            if tally:
                winner_name = max(tally, key=tally.get)
                if tally[winner_name] > 0:
                    data["winner"] = winner_name
                else:
                     data["winner"] = "No Valid Votes"

    global_winner = "Waiting..."
    if total_votes_casted > 0:
        global_winner = max(global_tally, key=global_tally.get)

    # Return Enhanced Stats
    return jsonify({
        "total_votes": total_votes_casted,
        "total_invalid": global_tally.get("Invalid vote", 0),
        "blocks_processed": len(chain_data),
        "global_winner": global_winner,
        "global_results": global_tally,
        "constituency_results": constituency_results
    })

# ==========================================
# 5. SYSTEM UTILITIES (PRESERVED)
# ==========================================

@app.route('/api/sys_reset', methods=['GET'])
def sys_reset():
    """Resets Blockchain Memory"""
    global vote_chain
    logger.warning("⚠ SYSTEM RESET COMMAND RECEIVED ⚠")
    vote_chain = Blockchain() 
    logger.warning("✔ Memory Wiped. Blockchain reset to Genesis.")
    return jsonify({"status": "CLEARED", "message": "Server memory reset successful."}), 200

@app.route('/chain', methods=['GET'])
def get_chain():
    return jsonify({'chain': vote_chain.chain, 'pending': vote_chain.pending_votes}), 200

@app.route('/explorer')
def explorer():
    """Visual Blockchain Explorer"""
    display_chain = []
    for block in vote_chain.chain:
        block_data = block.copy() 
        block_data['current_hash'] = Blockchain.hash(block)
        display_chain.append(block_data)
    return render_template('chain_explorer.html', chain=display_chain, pending=vote_chain.pending_votes)

@app.route('/api/validate_chain', methods=['GET'])
def validate_chain():
    """Cryptographic Check"""
    is_valid, message = vote_chain.is_chain_valid()
    status = "SECURE" if is_valid else "CORRUPTED"
    return jsonify({"status": status, "message": message}), (200 if is_valid else 500)

@app.route('/api/close_election', methods=['POST'])
def close_election():
    """Seal remaining votes"""
    if not vote_chain.pending_votes: return jsonify({"status": "EMPTY"})
    block = vote_chain.create_block(validator_id="ADMIN_FORCE_CLOSE")
    return jsonify({"status": "CLOSED", "message": f"Sealed remaining votes into Block #{block['index']}"})

@app.route('/api/verify_receipt', methods=['POST'])
def verify_receipt():
    """Search for vote receipt"""
    data = request.json
    target_alias = data.get('voter_alias', '').strip()
    
    for block in vote_chain.chain:
        for vote in block['votes']:
            if vote['voter_alias'] == target_alias:
                return jsonify({
                    "status": "FOUND", "location": "CHAIN",
                    "block_index": block['index'], "message": "✔ Vote Confirmed on Immutable Ledger."
                })
    for vote in vote_chain.pending_votes:
        if vote['voter_alias'] == target_alias:
            return jsonify({"status": "FOUND", "location": "MEMPOOL", "message": "⏳ In Mempool."})
            
    return jsonify({"status": "NOT_FOUND"}), 404

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

if __name__ == '__main__':
    print("[BACKEND] Voting Server Running on Port 5002...")
    app.run(port=5002, debug=True)