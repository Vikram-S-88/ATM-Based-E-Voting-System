import mysql.connector
from mysql.connector import errorcode
import os
from dotenv import load_dotenv
load_dotenv()

# Configuration
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_HOST = os.getenv('DB_HOST')

# Paths to your SQL files
SCHEMA_FILE = 'Voting_Phase/database/schema.sql'
SEED_FILE = 'Voting_Phase/database/seed_data.sql'

def create_database(cursor):
    try:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} DEFAULT CHARACTER SET 'utf8'")
        print(f"✔ Database '{DB_NAME}' created or already exists.")
    except mysql.connector.Error as err:
        print(f"✘ Failed creating database: {err}")
        exit(1)

def execute_sql_file(cursor, filename):
    print(f"\n--- Executing {filename} ---")
    
    if not os.path.exists(filename):
        print(f"✘ File {filename} not found!")
        return

    # [FIX] Added encoding='utf-8' to support Emojis 🗳️
    with open(filename, 'r', encoding='utf-8') as f:
        sql_file = f.read()

    # Split commands by semicolon (simple parser)
    commands = sql_file.split(';')

    for command in commands:
        try:
            # Skip empty lines
            if command.strip():
                cursor.execute(command)
                print(f"  ✔ Executed: {command[:40].replace(os.linesep, ' ')}...")
        except mysql.connector.Error as err:
            # Ignore "Table already exists" warnings if you want clean runs
            if err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
                print("  ⚠ Table already exists.")
            else:
                print(f"  ✘ Error: {err}")
                print(f"    Command: {command[:50]}...")
    
def main():
    # 1. Get Password securely
    db_password = 'vijay'
    print(f"Connecting to: {DB_HOST} as User: {DB_USER}")
    # 2. Connect to MySQL Server (No Database selected yet)
    try:
        cnx = mysql.connector.connect(
    user=DB_USER, 
    password=db_password, 
    host=DB_HOST,
    use_pure=True  # Forces the Python implementation which defaults to TCP
)
        cursor = cnx.cursor()
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("✘ Something is wrong with your user name or password")
        else:
            print(f"✘ Error: {err}")
        exit(1)

    # 3. Create and Select Database
    create_database(cursor)
    
    try:
        cnx.database = DB_NAME
    except mysql.connector.Error as err:
        print(f"✘ Database {DB_NAME} does not exist even after creation attempt.")
        exit(1)

    # 4. Execute Schema
    execute_sql_file(cursor, SCHEMA_FILE)

    # 5. Execute Seed Data
    execute_sql_file(cursor, SEED_FILE)

    # 6. Clean up
    cnx.commit()
    cursor.close()
    cnx.close()
    print("\n✔ Setup Complete! Database is ready.")

if __name__ == "__main__":
    main()