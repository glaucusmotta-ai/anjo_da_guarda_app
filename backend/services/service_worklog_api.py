from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import smtplib
import sqlite3
import ssl
import subprocess

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/api", tags=["worklog-api"])

COOKIE_NAME = "adg_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 dias
RESET_TTL_SECONDS = 60 * 30  # 30 min


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


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(_db_path(), check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_utc_iso() -> str:
    return _now_utc().isoformat()


def _utc_day_str(ts: Optional[datetime] = None) -> str:
    t = ts or _now_utc()
    return t.date().isoformat()


def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    try:
        rows = con.execute(f"PRAGMA table_info({table})").fetchall()
        return {r["name"] for r in rows}
    except Exception:
        return set()


def _ensure_columns(con: sqlite3.Connection, table: str, cols: Dict[str, str]) -> None:
    existing = _table_columns(con, table)
    changed = False
    for col, ddl in cols.items():
        if col not in existing:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
            changed = True
    if changed:
        con.commit()


def _ensure_password_resets_schema(con: sqlite3.Connection) -> None:
    """
    Tabela de reset com compatibilidade:
    - suporta token em texto OU token_hash
    """
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            email TEXT,
            token TEXT,
            token_hash TEXT,
            created_at_utc TEXT NOT NULL,
            expires_at_utc TEXT NOT NULL,
            used_at_utc TEXT,
            ip TEXT,
            user_agent TEXT
        );
        """
    )
    con.commit()

    _ensure_columns(
        con,
        "password_resets",
        {
            "email": "TEXT",
            "token": "TEXT",
            "token_hash": "TEXT",
            "created_at_utc": "TEXT",
            "expires_at_utc": "TEXT",
            "used_at_utc": "TEXT",
            "ip": "TEXT",
            "user_agent": "TEXT",
        },
    )

    try:
        cols = _table_columns(con, "password_resets")
        if "token_hash" in cols:
            con.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_password_resets_token_hash ON password_resets(token_hash);"
            )
        if "token" in cols:
            con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_password_resets_token ON password_resets(token);")
        con.execute("CREATE INDEX IF NOT EXISTS ix_password_resets_user ON password_resets(user_id);")
        con.commit()
    except Exception:
        pass


def _ensure_schema(con: sqlite3.Connection) -> None:
    # usuarios
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            nome TEXT,
            role TEXT,
            pass_salt TEXT,
            pass_hash TEXT,
            created_at_utc TEXT
        );
        """
    )
    con.commit()

    _ensure_columns(
        con,
        "usuarios",
        {
            "nome": "TEXT",
            "role": "TEXT",
            "pass_salt": "TEXT",
            "pass_hash": "TEXT",
            "created_at_utc": "TEXT",
        },
    )

    # auth_sessions
    con.execute(
        """
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
        """
    )
    con.commit()

    _ensure_columns(
        con,
        "auth_sessions",
        {
            "started_at_utc": "TEXT",
            "ended_at_utc": "TEXT",
            "start_source": "TEXT",
            "end_source": "TEXT",
            "ip": "TEXT",
            "last_ip": "TEXT",
            "user_agent": "TEXT",
        },
    )

    # work_sessions
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS work_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            day_utc TEXT,
            day TEXT,
            started_at_utc TEXT,
            started_at TEXT,
            ended_at_utc TEXT,
            ended_at TEXT,
            start_source TEXT,
            end_source TEXT,
            day_summary TEXT
        );
        """
    )
    con.commit()

    # ✅ Git snapshot deve ser em work_sessions (sessão do dia)
    _ensure_columns(
        con,
        "work_sessions",
        {
            "day_utc": "TEXT",
            "day": "TEXT",
            "started_at_utc": "TEXT",
            "started_at": "TEXT",
            "ended_at_utc": "TEXT",
            "ended_at": "TEXT",
            "start_source": "TEXT",
            "end_source": "TEXT",
            "day_summary": "TEXT",
            "git_repo": "TEXT",
            "git_branch_start": "TEXT",
            "git_head_start": "TEXT",
            "git_branch_end": "TEXT",
            "git_head_end": "TEXT",
            "git_dirty_end": "INTEGER",
        },
    )

    # backfill day_utc/day a partir do started_at*
    cols_ws = _table_columns(con, "work_sessions")
    if ("day_utc" in cols_ws or "day" in cols_ws) and ("started_at_utc" in cols_ws or "started_at" in cols_ws):
        try:
            if "day_utc" in cols_ws:
                con.execute(
                    """
                    UPDATE work_sessions
                       SET day_utc = substr(COALESCE(started_at_utc, started_at), 1, 10)
                     WHERE (day_utc IS NULL OR day_utc = '')
                       AND COALESCE(started_at_utc, started_at) IS NOT NULL
                       AND COALESCE(started_at_utc, started_at) <> '';
                    """
                )
            if "day" in cols_ws:
                con.execute(
                    """
                    UPDATE work_sessions
                       SET day = substr(COALESCE(started_at_utc, started_at), 1, 10)
                     WHERE (day IS NULL OR day = '')
                       AND COALESCE(started_at_utc, started_at) IS NOT NULL
                       AND COALESCE(started_at_utc, started_at) <> '';
                    """
                )
            con.commit()
        except Exception:
            pass

    # índice por dia (se existir)
    try:
        cols_ws2 = _table_columns(con, "work_sessions")
        day_col = "day_utc" if "day_utc" in cols_ws2 else ("day" if "day" in cols_ws2 else None)
        if day_col:
            con.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS ux_work_sessions_user_day ON work_sessions(user_id, {day_col});"
            )
            con.commit()
    except Exception:
        pass

    # work_entries (compat total)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS work_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_session_id INTEGER,
            session_id INTEGER,
            user_id INTEGER,
            ts_utc TEXT,
            ts TEXT,
            entry_type TEXT NOT NULL,
            title TEXT,
            content TEXT NOT NULL
        );
        """
    )
    con.commit()

    _ensure_columns(
        con,
        "work_entries",
        {
            "work_session_id": "INTEGER",
            "session_id": "INTEGER",
            "user_id": "INTEGER",
            "ts_utc": "TEXT",
            "ts": "TEXT",
            "entry_type": "TEXT",
            "title": "TEXT",
            "content": "TEXT",
        },
    )

    _ensure_password_resets_schema(con)


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
# Request helpers / cookie
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
    resp.delete_cookie(key=COOKIE_NAME, path="/", secure=secure, samesite="lax")


def _truthy(v: str) -> bool:
    s = (v or "").strip().lower()
    return s in ("1", "true", "yes", "y", "on")


# =========================
# Git helpers (enforcement)
# =========================
def _git_enabled() -> bool:
    # default OFF (só liga quando setar env)
    return _truthy(os.getenv("WORKLOG_GIT_ENFORCE", "0"))


def _git_repo_path() -> Path:
    p = (os.getenv("WORKLOG_REPO_PATH") or "").strip()
    if p:
        return Path(p).expanduser().resolve()
    return _root_dir()


def _git_run(args: list[str]) -> str:
    repo = _git_repo_path()
    if not (repo / ".git").exists():
        raise RuntimeError(f"WORKLOG_REPO_PATH não é repo git: {repo}")
    cp = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=8,
    )
    if cp.returncode != 0:
        err = (cp.stderr or cp.stdout or "").strip()
        raise RuntimeError(f"git {' '.join(args)} falhou: {err}")
    return (cp.stdout or "").strip()


def _git_dirty_details() -> tuple[bool, str]:
    """
    dirty=True se houver mudanças não commitadas.
    details = saída do git status --porcelain (ou erro).
    """
    repo = _git_repo_path()
    try:
        cp = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=8,
        )
        if cp.returncode != 0:
            err = (cp.stderr or cp.stdout or "").strip()
            return True, (err or "git status falhou")
        out = (cp.stdout or "").strip()
        return (len(out) > 0), out
    except Exception as e:
        return True, str(e)


def _git_snapshot() -> Dict[str, Any]:
    branch = _git_run(["rev-parse", "--abbrev-ref", "HEAD"])
    head = _git_run(["rev-parse", "HEAD"])
    dirty, details = _git_dirty_details()
    return {"repo": str(_git_repo_path()), "branch": branch, "head": head, "dirty": dirty, "details": details}


def _ws_set_git_start_if_needed(con: sqlite3.Connection, session_id: int) -> None:
    """
    Salva git_*_start na work_sessions se ainda não estiver preenchido.
    Só roda se _git_enabled() estiver ON.
    """
    if not _git_enabled():
        return

    cols = _table_columns(con, "work_sessions")
    needed = {"git_repo", "git_branch_start", "git_head_start"}
    if not needed.issubset(cols):
        return

    snap = _git_snapshot()

    con.execute(
        """
        UPDATE work_sessions
           SET git_repo=?,
               git_branch_start=?,
               git_head_start=?
         WHERE id=?
           AND (git_head_start IS NULL OR git_head_start='')
        """,
        (snap["repo"], snap["branch"], snap["head"], int(session_id)),
    )
    con.commit()


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


class ForgotBody(BaseModel):
    email: EmailStr


class ResetBody(BaseModel):
    token: str
    password: str


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
        return con.execute("SELECT id, email, nome, role FROM usuarios WHERE id=?", (user_id,)).fetchone()
    except sqlite3.OperationalError:
        return con.execute(
            "SELECT rowid as id, email, nome, role FROM usuarios WHERE rowid=?",
            (user_id,),
        ).fetchone()


def _insert_auth_session(con: sqlite3.Connection, user_id: int, token: str, source: str, req: Request) -> None:
    cols = _table_columns(con, "auth_sessions")
    now_dt = _now_utc()
    now = now_dt.isoformat()
    exp = (now_dt + timedelta(seconds=COOKIE_MAX_AGE)).isoformat()

    columns: list[str] = []
    params: list[Any] = []

    if "token" in cols:
        columns.append("token"); params.append(token)
    if "user_id" in cols:
        columns.append("user_id"); params.append(int(user_id))

    if "created_at_utc" in cols:
        columns.append("created_at_utc"); params.append(now)
    if "expires_at_utc" in cols:
        columns.append("expires_at_utc"); params.append(exp)

    if "started_at_utc" in cols:
        columns.append("started_at_utc"); params.append(now)
    if "start_source" in cols:
        columns.append("start_source"); params.append(source or "Web")
    if "last_ip" in cols:
        columns.append("last_ip"); params.append(_req_ip(req))
    if "ip" in cols:
        columns.append("ip"); params.append(_req_ip(req))
    if "user_agent" in cols:
        columns.append("user_agent"); params.append(_req_ua(req))

    qmarks = ",".join(["?"] * len(columns))
    sql = f"INSERT INTO auth_sessions ({', '.join(columns)}) VALUES ({qmarks})"
    con.execute(sql, params)


def _require_auth(req: Request) -> Dict[str, Any]:
    token = req.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="não autenticado")

    con = _connect()
    try:
        _ensure_schema(con)
        cols = _table_columns(con, "auth_sessions")

        select_cols = ["token", "user_id"]
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

        if "expires_at_utc" in row.keys():
            try:
                exp_dt = datetime.fromisoformat(str(row["expires_at_utc"]))
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if _now_utc() > exp_dt:
                    raise HTTPException(status_code=401, detail="sessão expirada")
            except HTTPException:
                raise
            except Exception:
                pass

        user = _get_user_by_id(con, int(row["user_id"]))
        if not user:
            raise HTTPException(status_code=401, detail="sessão inválida")

        return {
            "token": token,
            "user": {"id": int(user["id"]), "email": user["email"], "nome": user["nome"], "role": user["role"]},
        }
    finally:
        con.close()


# =========================
# AUTH endpoints
# =========================
@router.post("/auth/bootstrap")
def auth_bootstrap(body: BootstrapBody, req: Request):
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
            if "ended_at_utc" in cols:
                con.execute(
                    "UPDATE auth_sessions SET ended_at_utc=? WHERE token=? AND (ended_at_utc IS NULL OR ended_at_utc='')",
                    (_now_utc_iso(), token),
                )
                con.commit()

        resp = Response(content='{"ok":true}', media_type="application/json; charset=utf-8")
        _clear_cookie(resp, secure=_is_secure_request(req))
        return resp
    finally:
        con.close()


# =========================
# WORKLOG helpers
# =========================
def _ws_cols(con: sqlite3.Connection) -> Dict[str, Optional[str]]:
    cols = _table_columns(con, "work_sessions")
    day = "day_utc" if "day_utc" in cols else ("day" if "day" in cols else None)
    started = "started_at_utc" if "started_at_utc" in cols else ("started_at" if "started_at" in cols else None)
    ended = "ended_at_utc" if "ended_at_utc" in cols else ("ended_at" if "ended_at" in cols else None)
    return {
        "day": day,
        "started": started,
        "ended": ended,
        "start_source": "start_source" if "start_source" in cols else None,
        "end_source": "end_source" if "end_source" in cols else None,
        "day_summary": "day_summary" if "day_summary" in cols else None,
    }


def _we_cols(con: sqlite3.Connection) -> Dict[str, Any]:
    cols = _table_columns(con, "work_entries")
    sid_cols: list[str] = []
    if "work_session_id" in cols:
        sid_cols.append("work_session_id")
    if "session_id" in cols:
        sid_cols.append("session_id")

    return {
        "cols": cols,
        "sid_cols": sid_cols,
        "has_ts": "ts" in cols,
        "has_ts_utc": "ts_utc" in cols,
        "has_user_id": "user_id" in cols,
    }


def _ws_find_today(con: sqlite3.Connection, user_id: int, day: str) -> Optional[sqlite3.Row]:
    m = _ws_cols(con)
    day_col = m["day"]
    if not day_col:
        return None
    return con.execute(
        f"SELECT * FROM work_sessions WHERE user_id=? AND {day_col}=?",
        (user_id, day),
    ).fetchone()


# =========================
# WORKLOG endpoints
# =========================
@router.post("/worklog/start")
def worklog_start(body: StartBody, req: Request):
    auth = _require_auth(req)
    user_id = int(auth["user"]["id"])

    con = _connect()
    try:
        _ensure_schema(con)
        day = _utc_day_str()

        m = _ws_cols(con)
        day_col = m["day"]
        started_col = m["started"]
        ended_col = m["ended"]

        if not day_col or not started_col:
            raise HTTPException(status_code=500, detail="schema work_sessions inválido")

        row = con.execute(
            f"SELECT id, {started_col} as started, {ended_col} as ended "
            f"FROM work_sessions WHERE user_id=? AND {day_col}=?",
            (user_id, day),
        ).fetchone()

        # já existe e está aberta
        if row and not row["ended"]:
            # garante baseline git (se ainda não tem)
            _ws_set_git_start_if_needed(con, int(row["id"]))
            return {"ok": True, "session_id": int(row["id"]), "started_at": row["started"]}

        started_at = _now_utc_iso()

        # existe mas estava encerrada -> reabre
        if row and row["ended"]:
            sets: list[str] = []
            if ended_col:
                sets.append(f"{ended_col}=NULL")
            if m["end_source"]:
                sets.append(f"{m['end_source']}=NULL")
            if m["day_summary"]:
                sets.append(f"{m['day_summary']}=NULL")
            con.execute(f"UPDATE work_sessions SET {', '.join(sets)} WHERE id=?", (int(row["id"]),))
            con.commit()

            _ws_set_git_start_if_needed(con, int(row["id"]))
            return {"ok": True, "session_id": int(row["id"]), "started_at": row["started"]}

        # nova sessão do dia
        cols_ws = _table_columns(con, "work_sessions")

        insert_cols = ["user_id"]
        params2: list[Any] = [user_id]

        if day_col in cols_ws:
            insert_cols.append(day_col); params2.append(day)

        if "started_at_utc" in cols_ws:
            insert_cols.append("started_at_utc"); params2.append(started_at)
        if "started_at" in cols_ws:
            insert_cols.append("started_at"); params2.append(started_at)

        if m["start_source"]:
            insert_cols.append(m["start_source"]); params2.append(body.source or "Web")

        qmarks = ",".join(["?"] * len(insert_cols))
        con.execute(f"INSERT INTO work_sessions ({', '.join(insert_cols)}) VALUES ({qmarks})", params2)
        con.commit()

        sid = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])

        # baseline git da sessão (para exigir commit no stop)
        _ws_set_git_start_if_needed(con, sid)

        return {"ok": True, "session_id": sid, "started_at": started_at}
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

        s = _ws_find_today(con, user_id, day)
        if not s:
            return {"ok": True, "session": None, "entries": []}

        m = _ws_cols(con)

        we = _we_cols(con)
        sid_cols = we["sid_cols"]
        if not sid_cols:
            raise HTTPException(status_code=500, detail="schema work_entries inválido (sem session_id/work_session_id)")

        ts_select = "ts_utc as ts" if we["has_ts_utc"] else ("ts as ts" if we["has_ts"] else "NULL as ts")

        if len(sid_cols) == 2:
            where = f"({sid_cols[0]}=? OR {sid_cols[1]}=?)"
            params = (int(s["id"]), int(s["id"]))
        else:
            where = f"{sid_cols[0]}=?"
            params = (int(s["id"]),)

        entries = con.execute(
            f"SELECT {ts_select}, entry_type, title, content "
            f"FROM work_entries WHERE {where} "
            f"ORDER BY COALESCE(ts_utc, ts) ASC, id ASC",
            params,
        ).fetchall()

        started_val = s[m["started"]] if m["started"] else None
        ended_val = s[m["ended"]] if m["ended"] else None

        session_obj: Dict[str, Any] = {
            "id": int(s["id"]),
            "user_id": int(s["user_id"]),
            "started_at": started_val,
            "ended_at": ended_val,
        }
        if m["start_source"]:
            session_obj["start_source"] = s[m["start_source"]]
        if m["end_source"]:
            session_obj["end_source"] = s[m["end_source"]]
        if m["day_summary"]:
            session_obj["day_summary"] = s[m["day_summary"]]

        return {"ok": True, "session": session_obj, "entries": [dict(e) for e in entries]}
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

        m = _ws_cols(con)
        day_col = m["day"]
        ended_col = m["ended"]

        if not day_col:
            raise HTTPException(status_code=500, detail="schema work_sessions inválido")

        s = con.execute(
            f"SELECT id, {ended_col} as ended FROM work_sessions WHERE user_id=? AND {day_col}=?",
            (user_id, day),
        ).fetchone()

        if not s:
            raise HTTPException(status_code=400, detail="sessão não iniciada")
        if s["ended"]:
            raise HTTPException(status_code=400, detail="sessão já encerrada")

        et = (body.entry_type or "TASK").strip().upper()
        if et not in ("TASK", "NOTE", "EVIDENCE", "EMAIL"):
            raise HTTPException(status_code=400, detail="entry_type inválido")

        content = (body.content or "").strip()
        if not content:
            raise HTTPException(status_code=400, detail="content obrigatório")

        we = _we_cols(con)
        cols = we["cols"]
        sid = int(s["id"])
        now = _now_utc_iso()

        insert_cols: list[str] = []
        params: list[Any] = []

        if "session_id" in cols:
            insert_cols.append("session_id"); params.append(sid)
        if "work_session_id" in cols:
            insert_cols.append("work_session_id"); params.append(sid)

        if "user_id" in cols:
            insert_cols.append("user_id"); params.append(user_id)

        if "ts_utc" in cols:
            insert_cols.append("ts_utc"); params.append(now)
        if "ts" in cols:
            insert_cols.append("ts"); params.append(now)

        insert_cols.append("entry_type"); params.append(et)
        insert_cols.append("title"); params.append((body.title or "").strip() or None)
        insert_cols.append("content"); params.append(content)

        qmarks = ",".join(["?"] * len(insert_cols))
        con.execute(f"INSERT INTO work_entries ({', '.join(insert_cols)}) VALUES ({qmarks})", params)
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

        m = _ws_cols(con)
        day_col = m["day"]
        ended_col = m["ended"]

        if not day_col or not ended_col:
            raise HTTPException(status_code=500, detail="schema work_sessions inválido")

        cols_ws = _table_columns(con, "work_sessions")

        select_cols = ["id", f"{ended_col} as ended"]
        if "git_head_start" in cols_ws:
            select_cols.append("git_head_start")
        if "git_branch_start" in cols_ws:
            select_cols.append("git_branch_start")

        s = con.execute(
            f"SELECT {', '.join(select_cols)} FROM work_sessions WHERE user_id=? AND {day_col}=?",
            (user_id, day),
        ).fetchone()

        if not s:
            raise HTTPException(status_code=400, detail="sessão não iniciada")

        if s["ended"]:
            return {"ok": True}

        # ====== GIT ENFORCEMENT (obrigar commit para encerrar) ======
        if _git_enabled():
            start_head = str(s["git_head_start"]).strip() if ("git_head_start" in s.keys() and s["git_head_start"]) else ""

            try:
                snap = _git_snapshot()
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"git enforcement falhou: {e}")

            if snap["dirty"]:
                preview = ""
                if snap.get("details"):
                    lines = str(snap["details"]).splitlines()
                    preview = "\n" + "\n".join(lines[:20])
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Encerramento bloqueado: existem alterações pendentes no Git.\n"
                        "Faça commit (e push, se for sua regra) e tente novamente."
                        + preview
                    ),
                )

            if start_head and start_head == snap["head"]:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Encerramento bloqueado: nenhum commit novo desde o início da sessão.\n"
                        "Faça pelo menos 1 commit e tente novamente."
                    ),
                )

        # grava encerramento + (opcional) snapshot git final
        sets = [f"{ended_col}=?"]
        params: list[Any] = [_now_utc_iso()]

        if m["end_source"]:
            sets.append(f"{m['end_source']}=?")
            params.append(body.source or "Web")
        if m["day_summary"]:
            sets.append(f"{m['day_summary']}=?")
            params.append(body.day_summary)

        if _git_enabled():
            try:
                snap2 = _git_snapshot()
                if "git_branch_end" in cols_ws:
                    sets.append("git_branch_end=?"); params.append(snap2["branch"])
                if "git_head_end" in cols_ws:
                    sets.append("git_head_end=?"); params.append(snap2["head"])
                if "git_dirty_end" in cols_ws:
                    sets.append("git_dirty_end=?"); params.append(1 if snap2["dirty"] else 0)
            except Exception:
                pass

        params.append(int(s["id"]))
        con.execute(f"UPDATE work_sessions SET {', '.join(sets)} WHERE id=?", params)
        con.commit()
        return {"ok": True}
    finally:
        con.close()


# =========================
# Password reset helpers
# =========================
def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _env_first(*keys: str) -> str:
    for k in keys:
        v = os.getenv(k)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return ""


def _smtp_conf() -> Optional[Dict[str, Any]]:
    """
    SMTP DEDICADO para Worklog (não conflita com SOS / Assinaturas).
    Prioridade:
      1) WORKLOG_SMTP_*
      2) COMM_SMTP_*      (se você quiser reaproveitar o bloco comercial)
      3) EMAIL_*          (legacy)
      4) SMTP_*           (legacy)
    """
    if not _truthy(os.getenv("EMAIL_ENABLED", "true")):
        return None

    host = _env_first("WORKLOG_SMTP_HOST", "COMM_SMTP_HOST", "EMAIL_SMTP_HOST", "SMTP_HOST")
    port_s = _env_first("WORKLOG_SMTP_PORT", "COMM_SMTP_PORT", "EMAIL_SMTP_PORT", "SMTP_PORT") or "587"
    user = _env_first("WORKLOG_SMTP_USER", "COMM_SMTP_USER", "EMAIL_USERNAME", "SMTP_USER")
    pwd = _env_first("WORKLOG_SMTP_PASS", "COMM_SMTP_PASS", "EMAIL_PASSWORD", "SMTP_PASS")
    from_email = _env_first("WORKLOG_SMTP_FROM", "COMM_SMTP_FROM", "EMAIL_FROM", "SMTP_FROM", "SMTP_USER")
    from_name = _env_first("WORKLOG_SMTP_FROM_NAME", "COMM_SMTP_FROM_NAME", "EMAIL_FROM_NAME", "SMTP_FROM_NAME") or "Anjo Worklog"
    reply_to = _env_first("WORKLOG_SMTP_REPLY_TO", "COMM_SMTP_REPLY_TO", "EMAIL_REPLY_TO")

    try:
        port = int(port_s)
    except Exception:
        port = 587

    if not host or not user or not pwd or not from_email:
        return None

    return {
        "host": host,
        "port": port,
        "user": user,
        "pwd": pwd,
        "from_email": from_email,
        "from_name": from_name,
        "reply_to": reply_to,
    }


def _send_mail(to_email: str, subject: str, text: str) -> bool:
    conf = _smtp_conf()
    if not conf:
        print("[WORKLOG] SMTP não configurado (ou EMAIL_ENABLED=false).")
        return False

    msg = EmailMessage()
    msg["From"] = f'{conf["from_name"]} <{conf["from_email"]}>'
    msg["To"] = to_email
    msg["Subject"] = subject
    if conf.get("reply_to"):
        msg["Reply-To"] = conf["reply_to"]
    msg.set_content(text, subtype="plain", charset="utf-8")

    host = conf["host"]
    port = conf["port"]
    user = conf["user"]
    pwd = conf["pwd"]

    try:
        ctx = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=25, context=ctx) as s:
                s.login(user, pwd)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=25) as s:
                s.ehlo()
                s.starttls(context=ctx)
                s.ehlo()
                s.login(user, pwd)
                s.send_message(msg)
        return True
    except Exception as e:
        print("[WORKLOG] erro ao enviar e-mail:", repr(e))
        return False


def _public_base(req: Request) -> str:
    """
    Em produção: usa PUBLIC_BASE_URL.
    Em localhost: por padrão usa o host local (evita link apontando pro domínio público durante testes).
    Se quiser forçar o público mesmo em localhost, set WORKLOG_FORCE_PUBLIC_BASE=1.
    """
    force_public = _truthy(os.getenv("WORKLOG_FORCE_PUBLIC_BASE", "false"))
    host = (req.url.hostname or "").lower()
    is_local = host in ("127.0.0.1", "localhost", "::1")

    b = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if b and (force_public or not is_local):
        return b

    return str(req.base_url).rstrip("/")


def _build_reset_link(req: Request, token: str) -> str:
    # ✅ Página HTML está em /worklog/reset (UI)
    return f"{_public_base(req)}/worklog/reset?token={token}"


def _pr_cols(con: sqlite3.Connection) -> Dict[str, Any]:
    cols = _table_columns(con, "password_resets")
    return {
        "cols": cols,
        "has_token": "token" in cols,
        "has_token_hash": "token_hash" in cols,
        "has_email": "email" in cols,
    }


# =========================
# Password reset endpoints
# =========================
@router.post("/auth/forgot")
def auth_forgot(body: ForgotBody, req: Request):
    """
    Gera link de redefinição e envia por e-mail (se existir usuário).
    Sempre retorna ok=true para não vazar se o e-mail existe.
    """
    email = str(body.email).lower().strip()

    con = _connect()
    link: Optional[str] = None
    try:
        _ensure_schema(con)

        user = _get_user_by_email(con, email)
        if user:
            token = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")
            th = _token_hash(token)

            now_dt = _now_utc()
            exp_dt = now_dt + timedelta(seconds=RESET_TTL_SECONDS)
            link = _build_reset_link(req, token)

            pr = _pr_cols(con)
            cols = pr["cols"]

            insert_cols: list[str] = ["user_id", "created_at_utc", "expires_at_utc", "used_at_utc", "ip", "user_agent"]
            params: list[Any] = [int(user["id"]), now_dt.isoformat(), exp_dt.isoformat(), None, _req_ip(req), _req_ua(req)]

            if "email" in cols:
                insert_cols.append("email"); params.append(email)
            if "token_hash" in cols:
                insert_cols.append("token_hash"); params.append(th)
            if "token" in cols:
                insert_cols.append("token"); params.append(token)

            qmarks = ",".join(["?"] * len(insert_cols))
            con.execute(f"INSERT INTO password_resets ({', '.join(insert_cols)}) VALUES ({qmarks})", params)
            con.commit()

            txt = (
                "Olá!\n\n"
                "Recebemos uma solicitação de redefinição de senha do Anjo Worklog.\n\n"
                f"Para criar uma nova senha, abra este link (válido por 30 minutos):\n{link}\n\n"
                "Se você não solicitou isso, ignore este e-mail.\n"
            )
            sent = _send_mail(email, "Redefinição de senha — Anjo Worklog", txt)
            print(f"[WORKLOG][FORGOT] email={email} sent={sent} link={link}")

        resp: Dict[str, Any] = {"ok": True}

        # Debug local opcional: retorna o link no JSON só em localhost + env=1
        if (
            req.client
            and req.client.host in ("127.0.0.1", "::1")
            and _truthy(os.getenv("WORKLOG_DEBUG_RESET", "false"))
            and link
        ):
            resp["debug_reset_link"] = link

        return resp
    finally:
        con.close()


@router.get("/auth/reset")
def auth_reset_page(token: str = ""):
    # compat: links antigos (/api/auth/reset?token=...)
    token = (token or "").strip()
    if not token:
        return HTMLResponse("<h3>Token ausente.</h3>", status_code=400, headers={"Content-Type": "text/html; charset=utf-8"})
    return RedirectResponse(url=f"/worklog/reset?token={token}", status_code=302)


@router.post("/auth/reset")
def auth_reset(body: ResetBody, req: Request):
    token = (body.token or "").strip()
    new_pass = body.password or ""

    if len(token) < 20:
        raise HTTPException(status_code=400, detail="token inválido")
    if len(new_pass) < 8:
        raise HTTPException(status_code=400, detail="senha muito curta (mín. 8)")

    th = _token_hash(token)

    con = _connect()
    try:
        _ensure_schema(con)

        cols = _table_columns(con, "password_resets")
        has_token_hash = "token_hash" in cols
        has_token = "token" in cols

        if has_token_hash:
            row = con.execute(
                "SELECT id, user_id, expires_at_utc, used_at_utc FROM password_resets WHERE token_hash=?",
                (th,),
            ).fetchone()
        elif has_token:
            row = con.execute(
                "SELECT id, user_id, expires_at_utc, used_at_utc FROM password_resets WHERE token=?",
                (token,),
            ).fetchone()
        else:
            raise HTTPException(status_code=500, detail="schema password_resets inválido")

        if not row:
            raise HTTPException(status_code=400, detail="token inválido")
        if row["used_at_utc"]:
            raise HTTPException(status_code=400, detail="token já utilizado")

        try:
            exp_dt = datetime.fromisoformat(str(row["expires_at_utc"]))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if _now_utc() > exp_dt:
                raise HTTPException(status_code=400, detail="token expirado")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="token inválido")

        user_id = int(row["user_id"])
        hp = _hash_password(new_pass)

        con.execute(
            "UPDATE usuarios SET pass_salt=?, pass_hash=? WHERE id=?",
            (hp["salt"], hp["hash"], user_id),
        )
        con.execute(
            "UPDATE password_resets SET used_at_utc=? WHERE id=?",
            (_now_utc_iso(), int(row["id"])),
        )

        cols_s = _table_columns(con, "auth_sessions")
        if "ended_at_utc" in cols_s:
            con.execute(
                "UPDATE auth_sessions SET ended_at_utc=? WHERE user_id=? AND (ended_at_utc IS NULL OR ended_at_utc='')",
                (_now_utc_iso(), user_id),
            )

        con.commit()
        return {"ok": True}
    finally:
        con.close()
