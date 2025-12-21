import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parents[1] / "data" / "anjo.db"
con = sqlite3.connect(str(db_path))
cur = con.cursor()

print("DB =", db_path)

cols = [r[1] for r in cur.execute("PRAGMA table_info(live_sessions)")]
print("COLUMNS =", cols)

count = cur.execute("select count(*) from live_sessions").fetchone()[0]
print("COUNT =", count)

last = cur.execute("select * from live_sessions order by rowid desc limit 1").fetchone()
print("LAST =", last)

con.close()

