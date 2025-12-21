import os
import sqlite3
from services import service_auth_central as m

loader = getattr(m, "_load_env_from_file", None)
if callable(loader):
    loader()

p = m._db_path()
con = sqlite3.connect(p)
cur = con.cursor()

print("DB =", p)

# colunas reais
cols = cur.execute("PRAGMA table_info(central_sessions)").fetchall()
print("COLUMNS =", [c[1] for c in cols])

# últimas sessões (sem chutar nomes de coluna)
rows = cur.execute("select * from central_sessions order by id desc limit 5").fetchall()
print("LAST_ROWS =", rows)

con.close()
