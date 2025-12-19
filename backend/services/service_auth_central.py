import os
import sqlite3
import secrets
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

# auto_error=False para a gente conseguir auditar tentativa sem credenciais
security = HTTPBasic(auto_error=False)


def _load_env_from_file() -> None:
    """
    Carrega backend/.env e raiz/.env (se existirem), sem depender de systemd.
    """
    here = os.path.dirname(os.path.abspath(__file__))          # backend/services
    backend_dir = os.path.normpath(os.path.join(here, ".."))   # backend
    root_dir = os.path.normpath(os.path.join(backend_dir, ".."))

    candidates = [
        os.path.join(backend_dir, ".env"),
        os.path.join(root_dir, ".env"),
    ]

    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


def _root_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))          # backend/services
    backend_dir = os.path.normpath(os.path.join(here, ".."))   # backend
    return os.path.normpath(os.path.join(backend_dir, ".."))   # raiz


def _db_path() -> str:
    data_dir = os.path.join(_root_dir(), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "anjo.db")


def _ensure_audit_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS central_access_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts_utc TEXT NOT NULL,
        username TEXT,
        ip TEXT,
        path TEXT,
        ok INTEGER NOT NULL,
        reason TEXT,
        user_agent TEXT
    );
    """)
    conn.commit()


def _audit(username: str, ip: str, path: str, ok: bool, reason: str, user_agent: str) -> None:
    if os.getenv("CENTRAL_AUDIT", "0").strip() not in ("1", "true", "True", "YES", "yes"):
        return

    try:
        conn = sqlite3.connect(_db_path())
        try:
            _ensure_audit_table(conn)
            conn.execute(
                """
                INSERT INTO central_access_audit(ts_utc, username, ip, path, ok, reason, user_agent)
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    username or "",
                    ip or "",
                    path or "",
                    1 if ok else 0,
                    reason or "",
                    (user_agent or "")[:300],
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        # auditoria nunca pode derrubar o sistema
        pass


def _parse_central_users() -> Dict[str, str]:
    """
    CENTRAL_USERS=adm@x.com:senha1;contato@y.com:senha2
    Também aceita fallback CENTRAL_USER/CENTRAL_PASS.
    """
    users: Dict[str, str] = {}

    raw = os.getenv("CENTRAL_USERS", "").strip()
    if raw:
        for item in raw.split(";"):
            item = item.strip()
            if not item:
                continue
            if ":" not in item:
                continue
            u, p = item.split(":", 1)
            u = u.strip()
            p = p.strip()
            if u and p:
                users[u] = p

    # fallback (caso exista)
    u1 = os.getenv("CENTRAL_USER", "").strip()
    p1 = os.getenv("CENTRAL_PASS", "").strip()
    if u1 and p1 and u1 not in users:
        users[u1] = p1

    return users


def _raise_unauthorized() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autorizado",
        headers={"WWW-Authenticate": "Basic"},
    )


def require_central_auth(
    request: Request,
    credentials: Optional[HTTPBasicCredentials] = Depends(security),
) -> str:
    """
    Protege rotas administrativas (Central + APIs admin).
    Retorna o username autenticado (email).
    """
    _load_env_from_file()
    allowed = _parse_central_users()

    ip = (request.client.host if request.client else "") or ""
    path = request.url.path
    ua = request.headers.get("user-agent", "")

    if not allowed:
        # Sem config = falha explícita
        _audit("", ip, path, False, "NOT_CONFIGURED", ua)
        raise HTTPException(status_code=500, detail="CENTRAL_USERS não configurado no .env")

    if credentials is None:
        _audit("", ip, path, False, "MISSING_CREDENTIALS", ua)
        _raise_unauthorized()

    user = (credentials.username or "").strip()
    pwd = credentials.password or ""

    expected = allowed.get(user)
    if not expected:
        _audit(user, ip, path, False, "UNKNOWN_USER", ua)
        _raise_unauthorized()

    if not secrets.compare_digest(pwd, expected):
        _audit(user, ip, path, False, "BAD_PASSWORD", ua)
        _raise_unauthorized()

    _audit(user, ip, path, True, "OK", ua)
    return user
