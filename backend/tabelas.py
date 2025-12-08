# -*- coding: utf-8 -*-
"""
tabelas.py

Evolui a tabela 'assinaturas' para incluir campos de:
- desconto_centavos      (INT, default 0)
- vendedor_email         (TEXT, opcional)
- comissao_centavos      (INT, default 0)

Rode uma vez com:
  python .\tabelas.py
"""

import os
import sqlite3

# BASE_DIR = pasta backend
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# DATA_DIR = C:\dev\anjo_da_guarda_app\data
DATA_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "anjo.db")


def coluna_existe(conn: sqlite3.Connection, tabela: str, coluna: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({tabela});")
    for row in cur.fetchall():
        # row[1] = nome da coluna
        if row[1] == coluna:
            return True
    return False


def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        cur = conn.cursor()

        # 1) desconto_centavos
        if not coluna_existe(conn, "assinaturas", "desconto_centavos"):
            cur.execute(
                "ALTER TABLE assinaturas "
                "ADD COLUMN desconto_centavos INTEGER NOT NULL DEFAULT 0;"
            )
            print("[UPG] adicionada coluna desconto_centavos")

        # 2) vendedor_email
        if not coluna_existe(conn, "assinaturas", "vendedor_email"):
            cur.execute(
                "ALTER TABLE assinaturas "
                "ADD COLUMN vendedor_email TEXT;"
            )
            print("[UPG] adicionada coluna vendedor_email")

        # 3) comissao_centavos
        if not coluna_existe(conn, "assinaturas", "comissao_centavos"):
            cur.execute(
                "ALTER TABLE assinaturas "
                "ADD COLUMN comissao_centavos INTEGER NOT NULL DEFAULT 0;"
            )
            print("[UPG] adicionada coluna comissao_centavos")

        conn.commit()
        print(f"[UPG] tabelas.py OK em: {DB_PATH}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
