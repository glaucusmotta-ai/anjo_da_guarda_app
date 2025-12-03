# service_mapa.py
import os
import sqlite3
import logging
from typing import List, Dict, Any

logger = logging.getLogger("anjo_da_guarda")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "anjo.db")


def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def salvar_ponto_trilha(session_id: str, lat: float, lon: float, ts_utc: str) -> None:
    """
    Grava um ponto da trilha na tabela live_track_points.

    Estrutura criada por upgrade_live_track_points.py:

      CREATE TABLE IF NOT EXISTS live_track_points (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id TEXT NOT NULL,
          created_at_utc TEXT NOT NULL,
          lat REAL NOT NULL,
          lon REAL NOT NULL
      );
    """
    try:
        with _db() as con:
            con.execute(
                """
                INSERT INTO live_track_points (session_id, created_at_utc, lat, lon)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, ts_utc, float(lat), float(lon)),
            )
    except Exception as e:
        logger.error("[MAPA] erro ao salvar ponto: %s", e)


def listar_pontos_trilha(session_id: str) -> List[Dict[str, Any]]:
    """
    Lista todos os pontos da trilha de uma sessão, em ordem cronológica.

    Retorna uma lista de dicts com as chaves:
      id, session_id, lat, lon, ts
    onde 'ts' é o created_at_utc da tabela.
    """
    try:
        with _db() as con:
            rows = con.execute(
                """
                SELECT
                    id,
                    session_id,
                    created_at_utc AS ts,
                    lat,
                    lon
                FROM live_track_points
                WHERE session_id = ?
                ORDER BY created_at_utc ASC, id ASC
                """,
                (session_id,),
            ).fetchall()

        return [
            {
                "id": r["id"],
                "session_id": r["session_id"],
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
                "ts": r["ts"],
            }
            for r in rows
        ]
    except Exception as e:
        logger.error("[MAPA] erro ao listar pontos: %s", e)
        return []
