import os
import mysql.connector
import requests 

# Configuration
# [FIX] Use the same dynamic path logic as blockchain.py
base_dir = os.path.dirname(os.path.abspath(__file__))
CHAIN_FILE = os.path.join(base_dir, 'local_ledger.json')

VOTING_SERVER_URL = 'http://localhost:5002'

DB_CONFIG = {
    'host': 'localhost', 
    'user': 'root', 
    'password': 'vijay',
    'database': 'ec_voting_system'
}

def reset_environment():
    print("⚠ STARTING FACTORY RESET ⚠")

    # 1. Delete File
    # We check both possible locations just in case
    possible_paths = [
        CHAIN_FILE,
        os.path.join(base_dir, 'local_ledger.json'),
        'Voting_Phase/voting_phase/local_ledger.json'
    ]
    
    deleted = False
    for path in possible_paths:
        if os.path.exists(path):
            try:
                os.remove(path)
                print(f"✔ Deleted Blockchain Ledger: {path}")
                deleted = True
            except Exception as e:
                print(f"✘ Error deleting {path}: {e}")

    if not deleted:
        print("ℹ No blockchain file found (starting fresh).")

    # 2. Clear Database
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # We only reset the 'has_voted' flag so you don't have to re-register users every time
        cursor.execute("DELETE FROM registration_audit;")
        cursor.execute("DELETE FROM token_pool;")
        print("✔ Reset 'registration_audit' and 'token_pool'.")
        print("✔ Reset 'has_voted' flags (Users remain registered).")

        conn.commit()
        conn.close()
    except mysql.connector.Error as err:
        print(f"✘ Database Error: {err}")

    # 3. Wipe Server RAM
    try:
        print("⚡ Signaling Voting Server to wipe RAM...")
        response = requests.get(f'{VOTING_SERVER_URL}/api/sys_reset')
        if response.status_code == 200:
            print("✔ Server Memory Reset Successful!")
        else:
            print(f"✘ Server Error: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("⚠ Voting Server is offline. (RAM is already clear).")

    print("\n[SUCCESS] System Ready for New Test Run!")

if __name__ == "__main__":
    reset_environment()