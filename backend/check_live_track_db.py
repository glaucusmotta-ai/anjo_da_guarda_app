import os, sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", "data", "anjo.db"))

def show_table(cur, name):
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({name})").fetchall()]
    print(f"\n== {name} ==")
    print("COLUMNS =", cols)
    print("COUNT   =", cur.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
    rows = cur.execute(f"SELECT * FROM {name} ORDER BY 1 DESC LIMIT 3").fetchall()
    print("LAST_3  =", rows)

print("DB =", DB_PATH)
con = sqlite3.connect(DB_PATH)
cur = con.cursor()

tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("TABLES =", tables)

for t in ["live_track_sessions", "live_track_points"]:
    if t in tables:
        show_table(cur, t)
    else:
        print(f"\n== {t} ==\n(NÃO EXISTE)")

con.close()
