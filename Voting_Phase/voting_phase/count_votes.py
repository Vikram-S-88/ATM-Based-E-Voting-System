import json
import base64
import os
import mysql.connector
from collections import defaultdict
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from dotenv import load_dotenv

load_dotenv()

# Database Config to Fetch Dynamic Candidates
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'selva'),
    'database': os.getenv('DB_NAME', 'ec_voting_system')
}

def build_candidate_map():
    """Fetches candidates from DB and creates { '1': 'DMK', '2': 'AIADMK' ... }"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT id, party_name FROM candidates ORDER BY id ASC")
        rows = cursor.fetchall()
        conn.close()
        
        # Current Logic: ATM enumerates starting at 1. 
        # But DB IDs might start at 1, or 5, or 100.
        # To match ATM's `enumerate(list, 1)`, we should map 
        # the *Order Index* to the Name, not necessarily the *DB ID*.
        
        mapping = {}
        for idx, (db_id, name) in enumerate(rows, 1):
            mapping[str(idx)] = name
            
        print(f"✔ Candidate Map Built: {mapping}")
        return mapping
    except Exception as e:
        print(f"❌ DB Error: {e}")
        return {}

def count_votes():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Load Keys & Ledger
    key_path = os.path.join(base_dir, "votes_private.pem")
    try:
        with open(key_path, "rb") as key_file:
            private_key = serialization.load_pem_private_key(key_file.read(), password=None)
    except FileNotFoundError:
        print(f"❌ Error: {key_path} not found.")
        return

    try:
        with open(os.path.join(base_dir, "local_ledger.json"), "r") as f:
            chain = json.load(f)
    except FileNotFoundError:
        print("❌ No ledger found.")
        return

    # 2. Build Dynamic Map
    CANDIDATE_MAP = build_candidate_map()
    if not CANDIDATE_MAP:
        print("⚠️ Warning: Could not fetch candidates from DB. Results will show numbers only.")

    # 3. Decrypt & Tally
    global_tally = defaultdict(int)
    
    print(f"\n🔐 Decrypting {len(chain)} Blocks...")

    for block in chain:
        for vote in block['votes']:
            try:
                # Decrypt
                cipher_text = base64.b64decode(vote['vote_data'])
                plaintext = private_key.decrypt(
                    cipher_text,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                ).decode('utf-8')
                
                vote_number = plaintext.strip() 
                
                # Dynamic Mapping
                candidate_name = CANDIDATE_MAP.get(vote_number, f"Unknown ({vote_number})")
                global_tally[candidate_name] += 1
                
            except Exception as e:
                print(f"⚠️ Decryption failed: {e}")

    # 4. Results
    print("\n" + "="*50)
    print("FINAL RESULTS (Dynamic)")
    print("="*50)
    
    if not global_tally:
        print("  No votes found.")
    else:
        for cand, count in sorted(global_tally.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {cand}: {count} votes")

if __name__ == "__main__":
    count_votes()