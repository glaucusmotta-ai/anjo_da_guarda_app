# upgrade_assinaturas.py
#
# Cria (se não existir) a tabela de assinaturas no banco anjo.db
# para controlar todos os planos vendidos (site, Play Store, etc).

import os
import sqlite3

# Mesmo padrão dos outros scripts de upgrade (live_track, sos, etc.)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "anjo.db")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("PRAGMA foreign_keys = ON;")

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS assinaturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Quem é o dono da assinatura (e-mail usado no cadastro/Play Store)
                user_email TEXT NOT NULL,

                -- Nome do plano: ex.: 'Mensal individual', 'Anual família', etc.
                plano TEXT NOT NULL,

                -- Valor mensal em centavos (ex.: 2290 = R$ 22,90)
                valor_mensal_centavos INTEGER NOT NULL,

                -- Status atual: 'ativa', 'cancelada', 'inadimplente', 'trial'
                status TEXT NOT NULL DEFAULT 'ativa',

                -- Origem da venda: 'site' ou 'playstore' (no futuro 'apple')
                origem TEXT NOT NULL,

                -- Provedor de cobrança: 'stripe', 'google_play', 'apple_store', 'manual', etc.
                billing_provider TEXT,

                -- Id da assinatura/fatura no provedor (quando existir)
                external_id TEXT,

                -- Datas em UTC (ISO 8601, texto)
                data_inicio_utc TEXT NOT NULL,
                data_prox_cobranca_utc TEXT,
                data_cancelamento_utc TEXT,

                created_at_utc TEXT NOT NULL,
                updated_at_utc TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_assinaturas_email
                ON assinaturas (user_email);

            CREATE INDEX IF NOT EXISTS idx_assinaturas_status
                ON assinaturas (status);

            CREATE INDEX IF NOT EXISTS idx_assinaturas_origem
                ON assinaturas (origem);
            """
        )

        conn.commit()
        print("OK: tabela 'assinaturas' criada/atualizada em:", DB_PATH)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
