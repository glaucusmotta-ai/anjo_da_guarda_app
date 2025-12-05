# backend/upgrade_sos_events.py
import sqlite3
from pathlib import Path

# Usa o MESMO banco que você já tem aí
DB_PATH = Path(__file__).with_name("anjo_da_guarda.db")


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Tabela de eventos de SOS / métricas
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sos_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- Quando o disparo aconteceu (ISO8601)
            created_at TEXT NOT NULL,

            -- Snapshot do cliente
            user_phone TEXT,
            user_name  TEXT,

            -- Como foi disparado: 'pin_coacao', 'audio', 'quick_tile', 'botao_home'
            trigger_type TEXT NOT NULL,

            -- 1 = teste, 0 = ocorrência real
            is_test INTEGER NOT NULL DEFAULT 0,

            -- Região / perfil no momento do disparo
            region_city         TEXT,
            region_state        TEXT,
            region_neighborhood TEXT,
            cep                 TEXT,

            -- Canais usados (0/1) e status resumido
            channel_sms      INTEGER NOT NULL DEFAULT 0,
            channel_wa       INTEGER NOT NULL DEFAULT 0,
            channel_email    INTEGER NOT NULL DEFAULT 0,
            channel_telegram INTEGER NOT NULL DEFAULT 0,

            status_sms      TEXT,
            status_wa       TEXT,
            status_email    TEXT,
            status_telegram TEXT,

            -- Live tracking
            live_track_started      INTEGER NOT NULL DEFAULT 0,
            live_track_session_id   TEXT,
            live_track_duration_sec INTEGER,

            -- Info técnica (pra debug/KPI)
            app_version     TEXT,
            device_model    TEXT,
            android_version TEXT,
            gps_ok          INTEGER NOT NULL DEFAULT 0,

            -- Última localização conhecida
            lat REAL,
            lon REAL
        );
        """
    )

    conn.commit()
    conn.close()
    print("Tabela sos_events criada/atualizada com sucesso.")


if __name__ == "__main__":
    main()
