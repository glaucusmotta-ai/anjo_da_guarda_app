# backend/services/metrics.py
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Iterable, Mapping, Any, Optional

# Caminho padrão do banco anjo_da_guarda.db
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),  # sobe de services/ para backend/
    "anjo_da_guarda.db",
)


def _get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Abre conexão com o SQLite usando row_factory=Row.
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def registrar_sos_event(
    *,
    # Quem disparou
    user_phone: str | None = None,   # E.164 se possível
    user_name: str | None = None,
    # Como disparou
    trigger_source: str | None = None,  # ex: 'pin', 'audio', 'tile', 'button'
    trigger_mode: str | None = None,    # ex: 'silent', 'normal'
    # Canais utilizados
    channels: Iterable[str] | None = None,  # ex: ['wa', 'sms', 'tg', 'email']
    is_test: bool | None = None,           # True = teste; False = real
    # Localização aproximada
    lat: float | None = None,
    lon: float | None = None,
    cep: str | None = None,
    city: str | None = None,
    neighborhood: str | None = None,
    state: str | None = None,
    country: str | None = None,
    # Tracking / mapa
    map_session_id: str | None = None,
    tracking_url: str | None = None,
    # Qualquer coisa extra (JSON)
    extra: Mapping[str, Any] | None = None,
    # Opcional: outro caminho de banco
    db_path: str | None = None,
) -> int:
    """
    Registra um evento de SOS na tabela sos_events.

    A função é "defensiva": primeiro descobre quais colunas existem em
    sos_events e só grava nas que existem, para evitar erro se a tabela
    mudar no futuro.

    Retorna o ID (rowid) inserido, ou -1 em caso de erro.
    """
    conn = _get_connection(db_path)
    cur = conn.cursor()

    # Descobre colunas existentes na tabela
    cur.execute("PRAGMA table_info(sos_events)")
    cols_info = cur.fetchall()
    existing_cols = {row[1] for row in cols_info}  # row[1] = nome da coluna

    if not existing_cols:
        # Tabela não existe ou sem colunas -> não quebra o app, só loga
        print("[metrics] Aviso: tabela sos_events não encontrada.")
        return -1

    # Timestamp padrão (UTC) – se a tabela tiver created_at, usamos
    now_ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # Monta dicionário "candidato" com todos os campos que gostaríamos de ter
    # (só serão usados os que existirem na tabela).
    campos: dict[str, Any] = {}

    if "created_at" in existing_cols:
        campos["created_at"] = now_ts

    # Dados do usuário
    if user_phone is not None:
        if "user_phone" in existing_cols:
            campos["user_phone"] = user_phone
        elif "phone" in existing_cols:
            campos["phone"] = user_phone
    if user_name is not None and "user_name" in existing_cols:
        campos["user_name"] = user_name

    # Forma de disparo
    if trigger_source is not None and "trigger_source" in existing_cols:
        campos["trigger_source"] = trigger_source
    if trigger_mode is not None and "trigger_mode" in existing_cols:
        campos["trigger_mode"] = trigger_mode

    # Canais
    if channels is not None:
        canais_str = ",".join(channels)
        if "channels" in existing_cols:
            campos["channels"] = canais_str

    if is_test is not None:
        if "is_test" in existing_cols:
            campos["is_test"] = int(bool(is_test))  # 0/1
        elif "kind" in existing_cols:
            # em alguns esquemas podemos ter 'kind' = 'test'/'real'
            campos["kind"] = "test" if is_test else "real"

    # Localização
    if lat is not None and "lat" in existing_cols:
        campos["lat"] = float(lat)
    if lon is not None and "lon" in existing_cols:
        campos["lon"] = float(lon)
    if cep is not None and "cep" in existing_cols:
        campos["cep"] = cep
    if city is not None and "city" in existing_cols:
        campos["city"] = city
    if neighborhood is not None and "neighborhood" in existing_cols:
        campos["neighborhood"] = neighborhood
    if state is not None and "state" in existing_cols:
        campos["state"] = state
    if country is not None and "country" in existing_cols:
        campos["country"] = country

    # Tracking / mapa
    if map_session_id is not None and "map_session_id" in existing_cols:
        campos["map_session_id"] = map_session_id
    if tracking_url is not None and "tracking_url" in existing_cols:
        campos["tracking_url"] = tracking_url

    # Extra (JSON) – tenta encaixar em qualquer coluna típica de payload
    if extra is not None:
        extra_json = json.dumps(extra, ensure_ascii=False)
        for col in ("extra_json", "extra", "raw_payload"):
            if col in existing_cols:
                campos[col] = extra_json
                break

    if not campos:
        # Nenhuma coluna compatível -> não vamos quebrar o fluxo
        print("[metrics] Aviso: nenhuma coluna compatível em sos_events.")
        return -1

    # Monta o INSERT dinâmico
    col_names = ", ".join(campos.keys())
    placeholders = ", ".join(["?"] * len(campos))
    values = list(campos.values())

    sql = f"INSERT INTO sos_events ({col_names}) VALUES ({placeholders})"

    try:
        cur.execute(sql, values)
        conn.commit()
        rowid = cur.lastrowid
        print(f"[metrics] sos_events inserido com id={rowid}")
        return rowid
    except Exception as e:
        # Log simples – sem estourar exceção para não derrubar o fluxo de SOS
        print(f"[metrics] Erro ao inserir em sos_events: {e}")
        return -1
    finally:
        conn.close()
