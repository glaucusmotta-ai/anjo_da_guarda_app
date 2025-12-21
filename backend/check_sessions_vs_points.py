import sqlite3
from pathlib import Path

db_path = Path(__file__).resolve().parents[1] / "data" / "anjo.db"
con = sqlite3.connect(str(db_path))
cur = con.cursor()

print("DB =", db_path)

print("\n== LIVE_SESSIONS (last 10) ==")
rows = cur.execute("""
  SELECT id, session_token, active, started_at, expires_at, last_at, user_id
  FROM live_sessions
  ORDER BY id DESC
  LIMIT 10
""").fetchall()

for r in rows:
    _id, token, active, started_at, expires_at, last_at, user_id = r
    cnt = cur.execute("SELECT count(*) FROM live_track_points WHERE session_id=?", (token,)).fetchone()[0]
    lastp = cur.execute("""
      SELECT created_at_utc, lat, lon
      FROM live_track_points
      WHERE session_id=?
      ORDER BY id DESC
      LIMIT 1
    """, (token,)).fetchone()
    print(f"- id={_id} token={token} active={active} user_id={user_id} points={cnt} last_point={lastp}")

print("\n== TOP session_id em LIVE_TRACK_POINTS ==")
top = cur.execute("""
  SELECT session_id, count(*) AS c, max(created_at_utc) AS last_at
  FROM live_track_points
  GROUP BY session_id
  ORDER BY c DESC
  LIMIT 10
""").fetchall()

for t in top:
    print("-", t)

con.close()
