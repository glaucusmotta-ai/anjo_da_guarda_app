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
    cur = conn.cursor()
    try:
        conn.execute("PRAGMA foreign_keys=ON;")

        print(f"Usando banco em: {DB_PATH}")

        # Verifica se a tabela já existe
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='live_track_points'"
        )
        row = cur.fetchone()

        if not row:
            # Não existe ainda: cria já no formato novo (com ts)
            print("Tabela live_track_points NÃO existe. Criando com coluna 'ts'...")
            conn.executescript(
                """
                CREATE TABLE live_track_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    lat REAL NOT NULL,
                    lon REAL NOT NULL,
                    ts TEXT NOT NULL
                );
                CREATE INDEX idx_ltp_session_time
                    ON live_track_points(session_id, ts);
                """
            )
            print("Tabela live_track_points criada com sucesso.")
        else:
            # Já existe: só ajusta as colunas se precisar
            print("Tabela live_track_points já existe. Verificando colunas...")
            cur.execute("PRAGMA table_info(live_track_points)")
            cols = [r[1] for r in cur.fetchall()]
            print("Colunas atuais:", cols)

            if "ts" not in cols:
                print("Coluna 'ts' NÃO existe. Adicionando...")
                cur.execute("ALTER TABLE live_track_points ADD COLUMN ts TEXT")
                print("Coluna 'ts' adicionada com sucesso.")
            else:
                print("Coluna 'ts' já existe. Nada a fazer.")

        conn.commit()
        print("OK: live_track_points criada/ajustada em", DB_PATH)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
