from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/api", tags=["worklog-api"])

# =========================
# Auth cookie
# =========================

COOKIE_NAME = "adg_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 dias


# =========================
# DB helpers
# =========================

def _root_dir() -> Path:
    # .../backend/services/service_worklog_api.py -> parents[2] = repo root
    return Path(__file__).resolve().parents[2]


def _data_dir() -> Path:
    d = _root_dir() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _db_path() -> str:
    return str((_data_dir() / "anjo.db").resolve())


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_day_str(ts: Optional[datetime] = None) -> str:
    t = ts or datetime.now(timezone.utc)
    return t.date().isoformat()


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(_db_path(), check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def _table_info(con: sqlite3.Connection, table: str) -> Dict[str, sqlite3.Row]:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"]: r for r in rows}


def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    return set(_table_info(con, table).keys())


def _ensure_columns(con: sqlite3.Connection, table: str, cols: Dict[str, str]) -> None:
    existing = _table_columns(con, table)
    changed = False
    for col, ddl in cols.items():
        if col not in existing:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
            changed = True
    if changed:
        con.commit()


def _ensure_schema(con: sqlite3.Connection) -> None:
    # 1) usuarios (somente do worklog)
    con.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        nome TEXT,
        role TEXT,
        pass_salt TEXT,
        pass_hash TEXT,
        created_at_utc TEXT
    );
    """)
    con.commit()

    _ensure_columns(con, "usuarios", {
        "nome": "TEXT",
        "role": "TEXT",
        "pass_salt": "TEXT",
        "pass_hash": "TEXT",
        "created_at_utc": "TEXT",
    })

    # 2) auth_sessions (compatível com o seu DB real: token PK + created/expires NOT NULL)
    con.execute("""
    CREATE TABLE IF NOT EXISTS auth_sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at_utc TEXT NOT NULL,
        expires_at_utc TEXT NOT NULL,
        last_ip TEXT,
        user_agent TEXT,
        started_at_utc TEXT,
        ended_at_utc TEXT,
        start_source TEXT,
        end_source TEXT,
        ip TEXT
    );
    """)
    con.commit()

    # Se já existia, garante colunas “extras” que seu app usa
    _ensure_columns(con, "auth_sessions", {
        "started_at_utc": "TEXT",
        "ended_at_utc": "TEXT",
        "start_source": "TEXT",
        "end_source": "TEXT",
        "ip": "TEXT",
        "last_ip": "TEXT",
        "user_agent": "TEXT",
    })

    # 3) work_sessions
    con.execute("""
    CREATE TABLE IF NOT EXISTS work_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        day_utc TEXT,
        started_at_utc TEXT,
        ended_at_utc TEXT,
        start_source TEXT,
        end_source TEXT,
        day_summary TEXT
    );
    """)
    con.commit()

    _ensure_columns(con, "work_sessions", {
        "day_utc": "TEXT",
        "start_source": "TEXT",
        "end_source": "TEXT",
        "day_summary": "TEXT",
    })

    # backfill day_utc se faltando
    cols_ws = _table_columns(con, "work_sessions")
    if "day_utc" in cols_ws and "started_at_utc" in cols_ws:
        try:
            con.execute("""
                UPDATE work_sessions
                   SET day_utc = substr(started_at_utc, 1, 10)
                 WHERE (day_utc IS NULL OR day_utc = '')
                   AND (started_at_utc IS NOT NULL AND started_at_utc <> '')
            """)
            con.commit()
        except Exception:
            pass

    # índice (só se day_utc existir)
    try:
        if "day_utc" in _table_columns(con, "work_sessions"):
            con.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_work_sessions_user_day ON work_sessions(user_id, day_utc);"
            )
            con.commit()
    except Exception:
        pass

    # 4) work_entries
    con.execute("""
    CREATE TABLE IF NOT EXISTS work_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        work_session_id INTEGER NOT NULL,
        ts_utc TEXT NOT NULL,
        entry_type TEXT NOT NULL,
        title TEXT,
        content TEXT NOT NULL
    );
    """)
    con.commit()


# =========================
# Password hashing
# =========================

def _hash_password(password: str, salt: Optional[bytes] = None) -> Dict[str, str]:
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 150_000)
    return {"salt": salt.hex(), "hash": dk.hex()}


def _verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 150_000)
    return hmac.compare_digest(dk.hex(), hash_hex)


# =========================
# Request helpers
# =========================

def _req_ip(req: Request) -> str:
    return req.client.host if req.client else ""


def _req_ua(req: Request) -> str:
    return req.headers.get("user-agent", "")


def _is_secure_request(req: Request) -> bool:
    return (req.url.scheme or "").lower() == "https"


def _set_cookie(resp: Response, token: str, secure: bool) -> None:
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=COOKIE_MAX_AGE,
        path="/",
    )


def _clear_cookie(resp: Response, secure: bool) -> None:
    resp.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        secure=secure,
        samesite="lax",
    )


def _insert_auth_session(con: sqlite3.Connection, user_id: int, token: str, source: str, req: Request) -> None:
    cols = _table_info(con, "auth_sessions")  # name -> row

    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    exp = (now_dt + timedelta(seconds=COOKIE_MAX_AGE)).isoformat()

    columns: list[str] = []
    params: list[Any] = []

    def add(col: str, val: Any) -> None:
        if col in cols:
            columns.append(col)
            params.append(val)

    # essenciais
    add("token", token)
    add("user_id", int(user_id))

    # NOT NULL no seu DB
    add("created_at_utc", now)
    add("expires_at_utc", exp)

    # opcionais
    add("started_at_utc", now)
    add("start_source", source or "Web")
    add("last_ip", _req_ip(req))
    add("ip", _req_ip(req))
    add("user_agent", _req_ua(req))

    qmarks = ",".join(["?"] * len(columns))
    sql = f"INSERT INTO auth_sessions ({', '.join(columns)}) VALUES ({qmarks})"
    con.execute(sql, params)


# =========================
# Models
# =========================

class BootstrapBody(BaseModel):
    email: EmailStr
    password: str
    nome: Optional[str] = ""
    role: Optional[str] = "ADMIN"


class LoginBody(BaseModel):
    email: EmailStr
    password: str
    source: Optional[str] = "Web"


class StartBody(BaseModel):
    source: Optional[str] = "Web"


class EntryBody(BaseModel):
    entry_type: str
    title: Optional[str] = None
    content: str


class StopBody(BaseModel):
    source: Optional[str] = "Web"
    day_summary: Optional[str] = None


# =========================
# Auth helpers
# =========================

def _get_user_by_email(con: sqlite3.Connection, email: str) -> Optional[sqlite3.Row]:
    e = email.strip().lower()
    try:
        return con.execute(
            "SELECT id, email, nome, role, pass_salt, pass_hash FROM usuarios WHERE email=?",
            (e,),
        ).fetchone()
    except sqlite3.OperationalError:
        return con.execute(
            "SELECT rowid as id, email, nome, role, pass_salt, pass_hash FROM usuarios WHERE email=?",
            (e,),
        ).fetchone()


def _get_user_by_id(con: sqlite3.Connection, user_id: int) -> Optional[sqlite3.Row]:
    try:
        return con.execute(
            "SELECT id, email, nome, role FROM usuarios WHERE id=?",
            (user_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return con.execute(
            "SELECT rowid as id, email, nome, role FROM usuarios WHERE rowid=?",
            (user_id,),
        ).fetchone()


def _require_auth(req: Request) -> Dict[str, Any]:
    token = req.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="não autenticado")

    con = _connect()
    try:
        _ensure_schema(con)

        cols = _table_columns(con, "auth_sessions")
        select_cols = ["user_id", "token"]
        if "ended_at_utc" in cols:
            select_cols.append("ended_at_utc")
        if "expires_at_utc" in cols:
            select_cols.append("expires_at_utc")

        row = con.execute(
            f"SELECT {', '.join(select_cols)} FROM auth_sessions WHERE token=?",
            (token,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=401, detail="sessão inválida")

        if "ended_at_utc" in row.keys() and row["ended_at_utc"]:
            raise HTTPException(status_code=401, detail="sessão inválida")

        if "expires_at_utc" in row.keys() and row["expires_at_utc"]:
            try:
                exp = datetime.fromisoformat(str(row["expires_at_utc"]).replace("Z", "+00:00"))
                if exp <= datetime.now(timezone.utc):
                    raise HTTPException(status_code=401, detail="sessão expirada")
            except ValueError:
                pass

        user = _get_user_by_id(con, int(row["user_id"]))
        if not user:
            raise HTTPException(status_code=401, detail="sessão inválida")

        return {
            "token": token,
            "user": {
                "id": int(user["id"]),
                "email": user["email"],
                "nome": user["nome"],
                "role": user["role"],
            },
        }
    finally:
        con.close()


# =========================
# AUTH endpoints
# =========================

@router.post("/auth/bootstrap")
def auth_bootstrap(body: BootstrapBody, req: Request):
    """
    Cria (ou completa) o usuário ADMIN localmente (tabela usuarios do worklog).
    """
    con = _connect()
    try:
        _ensure_schema(con)

        email = str(body.email).lower().strip()
        user = _get_user_by_email(con, email)

        hp = _hash_password(body.password)

        if user:
            if not user["pass_salt"] or not user["pass_hash"]:
                con.execute(
                    "UPDATE usuarios SET nome=?, role=?, pass_salt=?, pass_hash=? WHERE email=?",
                    (body.nome or "", body.role or "ADMIN", hp["salt"], hp["hash"], email),
                )
                con.commit()
            else:
                raise HTTPException(status_code=400, detail="bootstrap já foi feito")
        else:
            con.execute(
                "INSERT INTO usuarios (email, nome, role, pass_salt, pass_hash, created_at_utc) VALUES (?,?,?,?,?,?)",
                (email, body.nome or "", body.role or "ADMIN", hp["salt"], hp["hash"], _now_utc_iso()),
            )
            con.commit()

        return {"ok": True}
    finally:
        con.close()


@router.post("/auth/login")
def auth_login(body: LoginBody, req: Request):
    con = _connect()
    try:
        _ensure_schema(con)

        email = str(body.email).lower().strip()
        user = _get_user_by_email(con, email)
        if not user or not user["pass_salt"] or not user["pass_hash"]:
            raise HTTPException(status_code=401, detail="credenciais inválidas")

        if not _verify_password(body.password, user["pass_salt"], user["pass_hash"]):
            raise HTTPException(status_code=401, detail="credenciais inválidas")

        token = base64.urlsafe_b64encode(secrets.token_bytes(24)).decode("utf-8").rstrip("=")

        _insert_auth_session(con, int(user["id"]), token, body.source or "Web", req)
        con.commit()

        resp = Response(content='{"ok":true}', media_type="application/json; charset=utf-8")
        _set_cookie(resp, token, secure=_is_secure_request(req))
        return resp
    finally:
        con.close()


@router.post("/auth/logout")
def auth_logout(req: Request):
    token = req.cookies.get(COOKIE_NAME)
    con = _connect()
    try:
        _ensure_schema(con)
        if token:
            cols = _table_columns(con, "auth_sessions")
            sets = []
            params = []
            if "ended_at_utc" in cols:
                sets.append("ended_at_utc=?")
                params.append(_now_utc_iso())
            if "end_source" in cols:
                sets.append("end_source=?")
                params.append("Web")

            if sets:
                params.append(token)
                con.execute(f"UPDATE auth_sessions SET {', '.join(sets)} WHERE token=?", params)
                con.commit()

        resp = Response(content='{"ok":true}', media_type="application/json; charset=utf-8")
        _clear_cookie(resp, secure=_is_secure_request(req))
        return resp
    finally:
        con.close()

# =========================
# WORKLOG endpoints
# =========================

def _ws_pick(cols: set[str], *names: str) -> Optional[str]:
    for n in names:
        if n in cols:
            return n
    return None


@router.post("/worklog/start")
def worklog_start(body: StartBody, req: Request):
    auth = _require_auth(req)
    user_id = int(auth["user"]["id"])

    con = _connect()
    try:
        _ensure_schema(con)

        day = _utc_day_str()
        started_at = _now_utc_iso()

        cols_ws = _table_columns(con, "work_sessions")
        id_col = _ws_pick(cols_ws, "id")  # se não existir, usa rowid no SELECT
        day_col = _ws_pick(cols_ws, "day_utc", "day")
        started_utc_col = _ws_pick(cols_ws, "started_at_utc")
        started_col = _ws_pick(cols_ws, "started_at")
        ended_utc_col = _ws_pick(cols_ws, "ended_at_utc")
        ended_col = _ws_pick(cols_ws, "ended_at")  # fallback antigo
        start_source_col = _ws_pick(cols_ws, "start_source")
        end_source_col = _ws_pick(cols_ws, "end_source")
        day_summary_col = _ws_pick(cols_ws, "day_summary")

        # --- busca sessão do dia (compatível com day/day_utc) ---
        select_cols = []
        if id_col:
            select_cols.append("id")
        else:
            select_cols.append("rowid as id")

        # traz ambos (se existirem) para resposta
        if started_utc_col:
            select_cols.append(started_utc_col)
        if started_col:
            select_cols.append(started_col)

        # ended pode ser ended_at_utc ou ended_at
        if ended_utc_col:
            select_cols.append(ended_utc_col)
        if ended_col:
            select_cols.append(ended_col)

        params = [user_id]
        where = "WHERE user_id=?"
        if day_col:
            where += f" AND {day_col}=?"
            params.append(day)

        row = con.execute(
            f"SELECT {', '.join(select_cols)} FROM work_sessions {where} LIMIT 1",
            tuple(params),
        ).fetchone()

        def _row_started(r: sqlite3.Row) -> str:
            if started_utc_col and r.get(started_utc_col):
                return r[started_utc_col]
            if started_col and r.get(started_col):
                return r[started_col]
            return started_at

        def _row_ended(r: sqlite3.Row) -> Optional[str]:
            if ended_utc_col and r.get(ended_utc_col):
                return r[ended_utc_col]
            if ended_col and r.get(ended_col):
                return r[ended_col]
            return None

        if row:
            ended_val = _row_ended(row)
            if not ended_val:
                return {"ok": True, "session_id": int(row["id"]), "started_at": _row_started(row)}

            # reabrir (zera ended/end_source/day_summary) se existir a sessão do dia
            sets = []
            uparams: list[Any] = []
            if ended_utc_col:
                sets.append(f"{ended_utc_col}=NULL")
            if ended_col:
                sets.append(f"{ended_col}=NULL")
            if end_source_col:
                sets.append(f"{end_source_col}=NULL")
            if day_summary_col:
                sets.append(f"{day_summary_col}=NULL")

            if sets:
                uparams.append(int(row["id"]))
                con.execute(
                    f"UPDATE work_sessions SET {', '.join(sets)} WHERE "
                    + ("id=?" if id_col else "rowid=?"),
                    tuple(uparams),
                )
                con.commit()

            return {"ok": True, "session_id": int(row["id"]), "started_at": _row_started(row)}

        # --- cria sessão do dia (insere started_at e started_at_utc se existirem) ---
        insert_cols = ["user_id"]
        insert_vals: list[Any] = [user_id]

        if day_col:
            insert_cols.append(day_col)
            insert_vals.append(day)

        if started_utc_col:
            insert_cols.append(started_utc_col)
            insert_vals.append(started_at)

        if started_col:
            insert_cols.append(started_col)
            insert_vals.append(started_at)

        if start_source_col:
            insert_cols.append(start_source_col)
            insert_vals.append(body.source or "Web")

        qmarks = ",".join(["?"] * len(insert_cols))
        sql = f"INSERT INTO work_sessions ({', '.join(insert_cols)}) VALUES ({qmarks})"
        con.execute(sql, tuple(insert_vals))
        con.commit()

        sid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {"ok": True, "session_id": int(sid), "started_at": started_at}

    finally:
        con.close()


@router.get("/worklog/today")
def worklog_today(req: Request):
    auth = _require_auth(req)
    user_id = int(auth["user"]["id"])

    con = _connect()
    try:
        _ensure_schema(con)
        day = _utc_day_str()

        cols_ws = _table_columns(con, "work_sessions")
        day_col = _ws_pick(cols_ws, "day_utc", "day")
        started_utc_col = _ws_pick(cols_ws, "started_at_utc")
        started_col = _ws_pick(cols_ws, "started_at")
        ended_utc_col = _ws_pick(cols_ws, "ended_at_utc")
        ended_col = _ws_pick(cols_ws, "ended_at")
        start_source_col = _ws_pick(cols_ws, "start_source")
        end_source_col = _ws_pick(cols_ws, "end_source")
        day_summary_col = _ws_pick(cols_ws, "day_summary")

        if day_col:
            s = con.execute(
                f"SELECT * FROM work_sessions WHERE user_id=? AND {day_col}=? LIMIT 1",
                (user_id, day),
            ).fetchone()
        else:
            # fallback: sem coluna de dia, pega a última do usuário
            s = con.execute(
                "SELECT * FROM work_sessions WHERE user_id=? ORDER BY rowid DESC LIMIT 1",
                (user_id,),
            ).fetchone()

        if not s:
            return {"ok": True, "session": None, "entries": []}

        started_at = None
        if started_utc_col and s.get(started_utc_col):
            started_at = s[started_utc_col]
        elif started_col and s.get(started_col):
            started_at = s[started_col]

        ended_at = None
        if ended_utc_col and s.get(ended_utc_col):
            ended_at = s[ended_utc_col]
        elif ended_col and s.get(ended_col):
            ended_at = s[ended_col]

        entries = con.execute(
            "SELECT ts_utc as ts, entry_type, title, content "
            "FROM work_entries WHERE work_session_id=? ORDER BY ts_utc ASC",
            (int(s["id"]),) if "id" in s.keys() else (int(s["rowid"]),),
        ).fetchall()

        return {
            "ok": True,
            "session": {
                "id": int(s["id"]) if "id" in s.keys() else int(s["rowid"]),
                "user_id": int(s["user_id"]),
                "started_at": started_at,
                "ended_at": ended_at,
                "start_source": s.get(start_source_col) if start_source_col else None,
                "end_source": s.get(end_source_col) if end_source_col else None,
                "day_summary": s.get(day_summary_col) if day_summary_col else None,
            },
            "entries": [dict(e) for e in entries],
        }

    finally:
        con.close()


@router.post("/worklog/entry")
def worklog_entry(body: EntryBody, req: Request):
    auth = _require_auth(req)
    user_id = int(auth["user"]["id"])

    con = _connect()
    try:
        _ensure_schema(con)
        day = _utc_day_str()

        cols_ws = _table_columns(con, "work_sessions")
        day_col = _ws_pick(cols_ws, "day_utc", "day")
        ended_utc_col = _ws_pick(cols_ws, "ended_at_utc")
        ended_col = _ws_pick(cols_ws, "ended_at")

        if day_col:
            s = con.execute(
                f"SELECT id, {ended_utc_col or 'NULL'} as ended_at_utc, {ended_col or 'NULL'} as ended_at "
                f"FROM work_sessions WHERE user_id=? AND {day_col}=? LIMIT 1",
                (user_id, day),
            ).fetchone()
        else:
            s = con.execute(
                f"SELECT id, {ended_utc_col or 'NULL'} as ended_at_utc, {ended_col or 'NULL'} as ended_at "
                "FROM work_sessions WHERE user_id=? ORDER BY rowid DESC LIMIT 1",
                (user_id,),
            ).fetchone()

        if not s:
            raise HTTPException(status_code=400, detail="sessão não iniciada")

        ended_val = s["ended_at_utc"] if s["ended_at_utc"] else s["ended_at"]
        if ended_val:
            raise HTTPException(status_code=400, detail="sessão já encerrada")

        et = (body.entry_type or "TASK").strip().upper()
        if et not in ("TASK", "NOTE", "EVIDENCE", "EMAIL"):
            raise HTTPException(status_code=400, detail="entry_type inválido")

        content = (body.content or "").strip()
        if not content:
            raise HTTPException(status_code=400, detail="content obrigatório")

        con.execute(
            "INSERT INTO work_entries (work_session_id, ts_utc, entry_type, title, content) VALUES (?,?,?,?,?)",
            (int(s["id"]), _now_utc_iso(), et, (body.title or "").strip() or None, content),
        )
        con.commit()
        return {"ok": True}

    finally:
        con.close()



@router.post("/worklog/stop")
def worklog_stop(body: StopBody, req: Request):
    auth = _require_auth(req)
    user_id = int(auth["user"]["id"])

    con = _connect()
    try:
        _ensure_schema(con)
        day = _utc_day_str()

        s = con.execute(
            "SELECT id, ended_at_utc FROM work_sessions WHERE user_id=? AND day_utc=?",
            (user_id, day),
        ).fetchone()

        if not s:
            raise HTTPException(status_code=400, detail="sessão não iniciada")

        if s["ended_at_utc"]:
            return {"ok": True}  # idempotente

        con.execute(
            "UPDATE work_sessions SET ended_at_utc=?, end_source=?, day_summary=? WHERE id=?",
            (_now_utc_iso(), body.source or "Web", body.day_summary, int(s["id"])),
        )
        con.commit()
        return {"ok": True}
    finally:
        con.close()
