import psycopg2
import sys
import os

# Dynamically add the parent/root directory to Python's search path
_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)
from config import load_config

def connect(config):
    """Connect to the PostgreSQL database server"""
    try:
        # Check if the config is a string (DATABASE_URL) or a dict (db_params.ini)
        if isinstance(config, str):
            conn = psycopg2.connect(config)
        else:
            conn = psycopg2.connect(**config)

        print("Connected to the PostgreSQL server safely.")
        return conn
    except (psycopg2.DatabaseError, Exception) as error:
        print(f"Connection error: {error}")
        return None


if __name__ == "__main__":
    config = load_config()
    conn = connect(config)
    if conn:
        conn.close()  # Cleanly close the test connection immediately
