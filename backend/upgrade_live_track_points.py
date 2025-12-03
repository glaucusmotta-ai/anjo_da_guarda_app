# upgrade_live_track_points.py

import os
import sqlite3

# Mesmo caminho do anjo_web_main.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "anjo.db")

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS live_track_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                created_at_utc TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_ltp_session_time
                ON live_track_points(session_id, created_at_utc);
            """
        )
        conn.commit()
        print("OK: tabela live_track_points criada/ajustada em", DB_PATH)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
