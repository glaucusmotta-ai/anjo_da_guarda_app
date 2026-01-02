import os
import sqlite3
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import APIRouter, Request, Response, HTTPException
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/api", tags=["auth-worklog"])

COOKIE_NAME = "adg_session"
SESSION_DAYS = 7

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()

def _root_dir() -> Path:
    return Path(__file__).resolve().parents[2]  # .../backend/services -> root

def _db_path() -> str:
    env = os.getenv("ANJO_DB_PATH")
    if env:
        return env
    return str(_root_dir() / "data" / "anjo.db")

def _conn():
    con = sqlite3.connect(_db_path())
    con.row_factory = sqlite3.Row
    return con

def _init_tables():
    with _conn() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          email TEXT NOT NULL UNIQUE,
          nome TEXT NOT NULL,
          role TEXT NOT NULL DEFAULT 'USER',
          password_hash TEXT NOT NULL,
          created_at TEXT NOT NULL
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS auth_sessions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          token TEXT NOT NULL UNIQUE,
          created_at TEXT NOT NULL,
          expires_at TEXT NOT NULL,
          source TEXT,
          revoked_at TEXT,
          FOREIGN KEY(user_id) REFERENCES usuarios(id)
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS work_sessions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          started_at TEXT NOT NULL,
          ended_at TEXT,
          start_source TEXT,
          end_source TEXT,
          day_summary TEXT,
          FOREIGN KEY(user_id) REFERENCES usuarios(id)
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS work_entries (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id INTEGER NOT NULL,
          ts TEXT NOT NULL,
          entry_type TEXT NOT NULL,
          title TEXT,
          content TEXT NOT NULL,
          FOREIGN KEY(session_id) REFERENCES work_sessions(id)
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS email_tokens (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          email TEXT NOT NULL,
          token TEXT NOT NULL,
          created_at TEXT NOT NULL,
          used_at TEXT
        )
        """)

_init_tables()

# ===== password hash (pbkdf2) =====
def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return dk.hex()

def _make_password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    return f"pbkdf2_sha256$200000${salt.hex()}${_hash_password(password, salt)}"

def _check_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False

def _cookie_secure(req: Request) -> bool:
    xf = (req.headers.get("x-forwarded-proto") or "").lower()
    if xf == "https":
        return True
    return req.url.scheme == "https"

def _get_user_by_session(req: Request):
    token = req.cookies.get(COOKIE_NAME)
    if not token:
        return None

    now = _utcnow().isoformat()
    with _conn() as con:
        row = con.execute("""
          SELECT u.id, u.email, u.nome, u.role, s.token, s.expires_at, s.revoked_at
          FROM auth_sessions s
          JOIN usuarios u ON u.id = s.user_id
          WHERE s.token = ?
        """, (token,)).fetchone()

    if not row:
        return None
    if row["revoked_at"]:
        return None
    if row["expires_at"] <= now:
        return None
    return {"id": row["id"], "email": row["email"], "nome": row["nome"], "role": row["role"]}

def _require_user(req: Request):
    u = _get_user_by_session(req)
    if not u:
        raise HTTPException(status_code=401, detail="não autenticado")
    return u

def _today_window_utc():
    now = _utcnow()
    day0 = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    day1 = day0 + timedelta(days=1)
    return day0, day1

def _get_today_session(user_id: int):
    day0, day1 = _today_window_utc()
    with _conn() as con:
        s = con.execute("""
          SELECT * FROM work_sessions
          WHERE user_id = ? AND started_at >= ? AND started_at < ?
          ORDER BY started_at DESC LIMIT 1
        """, (user_id, _iso(day0), _iso(day1))).fetchone()
    return dict(s) if s else None

def _get_entries(session_id: int):
    with _conn() as con:
        rows = con.execute("""
          SELECT ts, entry_type, title, content
          FROM work_entries
          WHERE session_id = ?
          ORDER BY ts ASC
        """, (session_id,)).fetchall()
    return [dict(r) for r in rows]

# ===== Schemas =====
class LoginIn(BaseModel):
    email: EmailStr
    password: str
    source: str | None = None

class ForgotIn(BaseModel):
    email: EmailStr

class StartIn(BaseModel):
    source: str | None = None

class EntryIn(BaseModel):
    entry_type: str
    title: str | None = None
    content: str

class StopIn(BaseModel):
    source: str | None = None
    day_summary: str | None = None

# ===== Auth =====
@router.post("/auth/login")
def login(req: Request, res: Response, data: LoginIn):
    with _conn() as con:
        u = con.execute("SELECT * FROM usuarios WHERE email = ?", (data.email.lower(),)).fetchone()
    if not u or not _check_password(data.password, u["password_hash"]):
        raise HTTPException(status_code=401, detail="credenciais inválidas")

    token = secrets.token_urlsafe(32)
    now = _utcnow()
    exp = now + timedelta(days=SESSION_DAYS)

    with _conn() as con:
        con.execute("""
          INSERT INTO auth_sessions(user_id, token, created_at, expires_at, source)
          VALUES(?,?,?,?,?)
        """, (u["id"], token, _iso(now), _iso(exp), data.source or "Web"))

    res.set_cookie(
        COOKIE_NAME, token,
        httponly=True,
        secure=_cookie_secure(req),
        samesite="lax",
        max_age=SESSION_DAYS * 86400,
        path="/"
    )
    return {"ok": True, "user": {"id": u["id"], "email": u["email"], "nome": u["nome"], "role": u["role"]}}

@router.post("/auth/logout")
def logout(req: Request, res: Response):
    token = req.cookies.get(COOKIE_NAME)
    if token:
        with _conn() as con:
            con.execute("UPDATE auth_sessions SET revoked_at=? WHERE token=? AND revoked_at IS NULL", (_iso(_utcnow()), token))
    res.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}

@router.post("/auth/forgot")
def forgot(data: ForgotIn):
    # anti-enumeração: sempre retorna ok
    token = secrets.token_urlsafe(24)
    with _conn() as con:
        con.execute(
            "INSERT INTO email_tokens(email, token, created_at) VALUES(?,?,?)",
            (data.email.lower(), token, _iso(_utcnow()))
        )
    # MVP: aqui depois vamos integrar envio real por e-mail (Zoho/SMTP) sem expor segredos
    return {"ok": True}

# ===== Worklog =====
@router.get("/worklog/today")
def today(req: Request):
    u = _require_user(req)
    s = _get_today_session(u["id"])
    if not s:
        return {"ok": True, "session": None, "entries": []}
    return {"ok": True, "session": s, "entries": _get_entries(s["id"])}

@router.post("/worklog/start")
def start(req: Request, data: StartIn):
    u = _require_user(req)
    s = _get_today_session(u["id"])
    if s and not s.get("ended_at"):
        return {"ok": True, "session_id": s["id"], "started_at": s["started_at"]}

    now = _utcnow()
    with _conn() as con:
        cur = con.execute("""
          INSERT INTO work_sessions(user_id, started_at, start_source)
          VALUES(?,?,?)
        """, (u["id"], _iso(now), data.source or "Web"))
        sid = cur.lastrowid

    return {"ok": True, "session_id": sid, "started_at": _iso(now)}

@router.post("/worklog/entry")
def add_entry(req: Request, data: EntryIn):
    u = _require_user(req)
    s = _get_today_session(u["id"])
    if not s or s.get("ended_at"):
        # auto-start se não houver sessão ativa
        now = _utcnow()
        with _conn() as con:
            cur = con.execute("""
              INSERT INTO work_sessions(user_id, started_at, start_source)
              VALUES(?,?,?)
            """, (u["id"], _iso(now), "Web"))
            sid = cur.lastrowid
        s = _get_today_session(u["id"])

    now = _utcnow()
    with _conn() as con:
        con.execute("""
          INSERT INTO work_entries(session_id, ts, entry_type, title, content)
          VALUES(?,?,?,?,?)
        """, (s["id"], _iso(now), data.entry_type, data.title, data.content))

    return {"ok": True}

@router.post("/worklog/stop")
def stop(req: Request, data: StopIn):
    u = _require_user(req)
    s = _get_today_session(u["id"])
    if not s:
        raise HTTPException(status_code=400, detail="sem sessão")
    if s.get("ended_at"):
        return {"ok": True}

    now = _utcnow()
    with _conn() as con:
        con.execute("""
          UPDATE work_sessions
          SET ended_at=?, end_source=?, day_summary=COALESCE(?, day_summary)
          WHERE id=?
        """, (_iso(now), data.source or "Web", data.day_summary, s["id"]))

    return {"ok": True}
