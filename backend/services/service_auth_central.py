import os
import sqlite3
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

# auto_error=False para auditar tentativa sem credenciais
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
            # nunca derruba
            pass


def _root_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))          # backend/services
    backend_dir = os.path.normpath(os.path.join(here, ".."))   # backend
    return os.path.normpath(os.path.join(backend_dir, ".."))   # raiz


def _db_path() -> str:
    data_dir = os.path.join(_root_dir(), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "anjo.db")


# =========================================================
# AUDITORIA (opcional)
# =========================================================

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
    _load_env_from_file()
    if os.getenv("CENTRAL_AUDIT", "0").strip().lower() not in ("1", "true", "yes", "on"):
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
        # auditoria nunca derruba o sistema
        pass


# =========================================================
# USERS (CENTRAL_USERS)
# =========================================================

def _parse_central_users() -> Dict[str, str]:
    """
    CENTRAL_USERS=adm@x.com:senha1;contato@y.com:senha2
    Também aceita fallback CENTRAL_USER/CENTRAL_PASS.
    """
    _load_env_from_file()
    users: Dict[str, str] = {}

    raw = os.getenv("CENTRAL_USERS", "").strip()
    if raw:
        for item in raw.split(";"):
            item = item.strip()
            if not item or ":" not in item:
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


def central_validate_credentials(username: str, password: str) -> bool:
    allowed = _parse_central_users()
    user = (username or "").strip()
    pwd = password or ""
    expected = allowed.get(user)
    if not expected:
        return False
    return secrets.compare_digest(pwd, expected)


def _raise_unauthorized_basic() -> None:
    # usado apenas no Basic Auth (se você usar em endpoints de API)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autorizado",
        headers={"WWW-Authenticate": "Basic"},
    )


def _raise_unauthorized_session() -> None:
    # usado para sessão por cookie (não abre popup Basic)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autorizado",
    )


def require_central_auth(
    request: Request,
    credentials: Optional[HTTPBasicCredentials] = Depends(security),
) -> str:
    """
    Basic Auth (opcional).
    Retorna o username autenticado.
    """
    allowed = _parse_central_users()

    ip = (request.client.host if request.client else "") or ""
    path = request.url.path
    ua = request.headers.get("user-agent", "")

    if not allowed:
        _audit("", ip, path, False, "NOT_CONFIGURED", ua)
        raise HTTPException(status_code=500, detail="CENTRAL_USERS não configurado no .env")

    if credentials is None:
        _audit("", ip, path, False, "MISSING_CREDENTIALS", ua)
        _raise_unauthorized_basic()

    user = (credentials.username or "").strip()
    pwd = credentials.password or ""

    expected = allowed.get(user)
    if not expected:
        _audit(user, ip, path, False, "UNKNOWN_USER", ua)
        _raise_unauthorized_basic()

    if not secrets.compare_digest(pwd, expected):
        _audit(user, ip, path, False, "BAD_PASSWORD", ua)
        _raise_unauthorized_basic()

    _audit(user, ip, path, True, "OK", ua)
    return user


# =========================================================
# SESSÃO POR COOKIE (DB) para /central (Login HTML)
# =========================================================

def _cookie_name() -> str:
    _load_env_from_file()
    v = (os.getenv("CENTRAL_COOKIE_NAME") or "central_session").strip()
    return v or "central_session"


# Compatibilidade com imports antigos (ex.: anjo_web_main.py)
CENTRAL_COOKIE_NAME = _cookie_name()


def _session_ttl_min() -> int:
    _load_env_from_file()
    raw = (os.getenv("CENTRAL_SESSION_TTL_MIN") or "60").strip()
    try:
        return max(5, int(raw))
    except Exception:
        return 60


def _cookie_secure_flag() -> bool:
    _load_env_from_file()
    raw = (os.getenv("CENTRAL_COOKIE_SECURE", "1") or "1").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _session_secret() -> str:
    """
    Secret para hashear o token antes de salvar no DB.
    NÃO salva token puro no DB.
    """
    _load_env_from_file()
    secret = (os.getenv("CENTRAL_SESSION_SECRET") or "").strip()
    if not secret or len(secret) < 16:
        raise HTTPException(
            status_code=500,
            detail="CENTRAL_SESSION_SECRET não configurado (ou muito curto)."
        )
    return secret


def _hash_session_token(token: str) -> str:
    secret = _session_secret().encode("utf-8")
    msg = token.encode("utf-8")
    return hashlib.sha256(secret + b"|" + msg).hexdigest()


def _ensure_sessions_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS central_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token_hash TEXT UNIQUE NOT NULL,
        username TEXT NOT NULL,
        created_at_utc TEXT NOT NULL,
        expires_at_utc TEXT NOT NULL,
        last_seen_utc TEXT,
        ip TEXT,
        user_agent TEXT,
        revoked INTEGER DEFAULT 0
    );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_central_sessions_user ON central_sessions(username);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_central_sessions_exp ON central_sessions(expires_at_utc);")
    conn.commit()


def create_central_session(username: str, ip: str, user_agent: str) -> str:
    """
    Cria sessão no DB e devolve o TOKEN (vai no cookie HttpOnly).
    """
    token = secrets.token_urlsafe(32)
    token_hash = _hash_session_token(token)

    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=_session_ttl_min())

    conn = sqlite3.connect(_db_path())
    try:
        _ensure_sessions_table(conn)
        conn.execute(
            """
            INSERT INTO central_sessions(
              token_hash, username, created_at_utc, expires_at_utc,
              last_seen_utc, ip, user_agent, revoked
            )
            VALUES(?,?,?,?,?,?,?,0)
            """,
            (
                token_hash,
                (username or "").strip(),
                now.isoformat(),
                exp.isoformat(),
                now.isoformat(),
                (ip or "")[:80],
                (user_agent or "")[:300],
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return token


def revoke_central_session(token: str) -> None:
    if not token:
        return
    token_hash = _hash_session_token(token)
    conn = sqlite3.connect(_db_path())
    try:
        _ensure_sessions_table(conn)
        conn.execute("UPDATE central_sessions SET revoked=1 WHERE token_hash=?", (token_hash,))
        conn.commit()
    finally:
        conn.close()


def validate_central_session(token: str, request: Optional[Request] = None) -> str:
    """
    Valida cookie e retorna username.
    """
    if not token:
        _raise_unauthorized_session()

    token_hash = _hash_session_token(token)

    ip = ""
    path = ""
    ua = ""
    if request is not None:
        ip = (request.client.host if request.client else "") or ""
        path = request.url.path
        ua = request.headers.get("user-agent", "") or ""

    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    try:
        _ensure_sessions_table(conn)

        row = conn.execute(
            "SELECT username, expires_at_utc, revoked FROM central_sessions WHERE token_hash=?",
            (token_hash,),
        ).fetchone()

        if not row:
            _audit("", ip, path, False, "SESSION_NOT_FOUND", ua)
            _raise_unauthorized_session()

        if int(row["revoked"] or 0) == 1:
            _audit(str(row["username"]), ip, path, False, "SESSION_REVOKED", ua)
            _raise_unauthorized_session()

        try:
            exp = datetime.fromisoformat(row["expires_at_utc"])
        except Exception:
            exp = None

        now = datetime.now(timezone.utc)
        if not exp or now > exp:
            conn.execute("UPDATE central_sessions SET revoked=1 WHERE token_hash=?", (token_hash,))
            conn.commit()
            _audit(str(row["username"]), ip, path, False, "SESSION_EXPIRED", ua)
            _raise_unauthorized_session()

        # ok -> atualiza last_seen se tiver request
        if request is not None:
            conn.execute(
                "UPDATE central_sessions SET last_seen_utc=?, ip=?, user_agent=? WHERE token_hash=?",
                (now.isoformat(), (ip or "")[:80], (ua or "")[:300], token_hash),
            )
            conn.commit()
            _audit(str(row["username"]), ip, path, True, "SESSION_OK", ua)

        return str(row["username"])
    finally:
        conn.close()


def require_central_session(request: Request) -> str:
    token = request.cookies.get(_cookie_name())
    return validate_central_session(token, request)


# =========================================================
# COOKIE HELPERS (compatível com anjo_web_main.py)
# =========================================================

def set_central_session_cookie(response, token: str) -> None:
    """
    Recebe o TOKEN já criado por create_central_session() e grava no cookie.

    Agora: o cookie expira no navegador no mesmo TTL da sessão do servidor,
    evitando “cookie velho” que fica no browser e depois dá 401.
    """
    ttl_sec = _session_ttl_min() * 60
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_sec)

    response.set_cookie(
        key=_cookie_name(),
        value=token,
        httponly=True,
        secure=_cookie_secure_flag(),
        samesite="lax",
        path="/",
        max_age=ttl_sec,
        expires=expires_at,  # pode remover esta linha se quiser só max_age
    )


def clear_central_session_cookie(response) -> None:
    response.delete_cookie(key=_cookie_name(), path="/")


def central_user_from_request(request: Request) -> Optional[str]:
    token = request.cookies.get(_cookie_name())
    if not token:
        return None
    try:
        return validate_central_session(token, request)
    except Exception:
        return None

