from __future__ import annotations

import os
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request

# Reusa a autenticação do Worklog (cookie adg_session)
from services.service_worklog_api import _ensure_columns, _require_auth  # type: ignore

router = APIRouter(prefix="/api", tags=["worklog-workspace"])


# =========================================
# DB helpers (mesmo padrão do worklog_api)
# =========================================
def _root_dir() -> Path:
    # ...\backend\services\service_worklog_workspace.py -> parents[2] = raiz do repo
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


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workspace_enabled() -> bool:
    # Default: DESLIGADO
    return (os.getenv("WORKLOG_WORKSPACE_ENABLED") or "").strip() == "1"


def _workspace_provider() -> Optional[str]:
    # "local_vscode" | "codeserver" | "placeholder" ...
    p = (os.getenv("WORKLOG_WORKSPACE_PROVIDER") or "").strip()
    return p or None


def _workspace_path() -> Path:
    # Pasta que será aberta no VS Code (local)
    raw = (os.getenv("WORKLOG_WORKSPACE_PATH") or "").strip()
    p = Path(raw) if raw else _root_dir()
    try:
        p = p.resolve()
    except Exception:
        pass
    if not p.exists():
        return _root_dir()
    return p


def _vscode_url_for_path(p: Path) -> str:
    # Ex: vscode://file/C:/dev/anjo_da_guarda_app
    posix = p.as_posix()
    safe = "/:"  # mantém / e : para "C:/..."
    encoded = urllib.parse.quote(posix, safe=safe)
    return f"vscode://file/{encoded}"


def _ensure_workspace_schema(con: sqlite3.Connection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            created_at_utc TEXT NOT NULL,
            status TEXT,
            provider TEXT,
            workspace_url TEXT,
            repo TEXT,
            branch TEXT,
            last_seen_utc TEXT
        );
        """
    )
    con.commit()

    _ensure_columns(
        con,
        "workspace_sessions",
        {
            "user_id": "INTEGER",
            "created_at_utc": "TEXT",
            "status": "TEXT",
            "provider": "TEXT",
            "workspace_url": "TEXT",
            "repo": "TEXT",
            "branch": "TEXT",
            "last_seen_utc": "TEXT",
        },
    )

    try:
        con.execute("CREATE INDEX IF NOT EXISTS ix_workspace_sessions_user ON workspace_sessions(user_id);")
        con.commit()
    except Exception:
        pass


def _status_payload(
    enabled: bool,
    provider: Optional[str],
    status: str,
    workspace_url: Optional[str],
    message: str,
) -> Dict[str, Any]:
    return {
        "ok": True,
        "enabled": enabled,
        "provider": provider,
        "status": status,
        "workspace_url": workspace_url,
        "message": message,
    }

def _vscode_url_for_repo(repo_path: str) -> str:
    p = (repo_path or "").strip()
    if not p:
        return ""
    try:
        p = str(Path(p).resolve())
    except Exception:
        pass
    p = p.replace("\\", "/")
    p = urllib.parse.quote(p, safe="/:")
    return f"vscode://file/{p}"


@router.get("/workspace/status")
def workspace_status(req: Request):
    auth = _require_auth(req)
    user_id = int(auth["user"]["id"])

    enabled = _workspace_enabled()
    provider = _workspace_provider()

    con = _connect()
    try:
        _ensure_workspace_schema(con)

        row = con.execute(
            """
            SELECT id, status, provider, workspace_url
              FROM workspace_sessions
             WHERE user_id=?
             ORDER BY id DESC
             LIMIT 1
            """,
            (user_id,),
        ).fetchone()

        if not enabled:
            return _status_payload(
                enabled=False,
                provider=None,
                status="disabled",
                workspace_url=(row["workspace_url"] if row and row["workspace_url"] else None),
                message="Workspace ainda não configurado (Caminho A em implementação).",
            )

        if not provider:
            return _status_payload(
                enabled=True,
                provider=None,
                status="enabled_no_provider",
                workspace_url=(row["workspace_url"] if row and row["workspace_url"] else None),
                message="Workspace habilitado, mas provider ainda não configurado.",
            )

        # Provider local_vscode: já devolve URL mesmo sem sessão salva
        if provider == "local_vscode":
            url = _vscode_url_for_path(_workspace_path())
            return _status_payload(
                enabled=True,
                provider=provider,
                status=(row["status"] if row and row["status"] else "ready"),
                workspace_url=url,
                message="Workspace pronto (VS Code local). Clique em Abrir Workspace.",
            )

        # Provider placeholder/codeserver: usa o último estado salvo
        if not row:
            return _status_payload(
                enabled=True,
                provider=provider,
                status="ready",
                workspace_url=None,
                message="Workspace habilitado. Use Start para abrir.",
            )

        return _status_payload(
            enabled=True,
            provider=(row["provider"] or provider),
            status=(row["status"] or "unknown"),
            workspace_url=(row["workspace_url"] or None),
            message="Workspace status carregado.",
        )
    finally:
        con.close()


@router.post("/workspace/start")
def workspace_start(req: Request):
    auth = _require_auth(req)
    user_id = int(auth["user"]["id"])

    enabled = _workspace_enabled()
    provider = _workspace_provider()

    if not enabled:
        return _status_payload(False, None, "disabled", None, "Workspace ainda não configurado (Caminho A em implementação).")

    if not provider:
        return _status_payload(True, None, "enabled_no_provider", None, "Provider ainda não configurado.")

    # PASSO 1 FUNCIONAL (local): abre VS Code instalado na máquina do usuário
    if provider == "local_vscode":
        workspace_url = _vscode_url_for_path(_workspace_path())
        con = _connect()
        try:
            _ensure_workspace_schema(con)
            con.execute(
                """
                INSERT INTO workspace_sessions (user_id, created_at_utc, status, provider, workspace_url, last_seen_utc)
                VALUES (?,?,?,?,?,?)
                """,
                (user_id, _now_utc_iso(), "running", provider, workspace_url, _now_utc_iso()),
            )
            con.commit()
        finally:
            con.close()

        return _status_payload(True, provider, "running", workspace_url, "Abrindo VS Code local…")

    # Default: placeholder (prepara para passo 3/4: code-server/IDE web)
    workspace_url = f"/ide/{user_id}/"

    con = _connect()
    try:
        _ensure_workspace_schema(con)
        con.execute(
            """
            INSERT INTO workspace_sessions (user_id, created_at_utc, status, provider, workspace_url, last_seen_utc)
            VALUES (?,?,?,?,?,?)
            """,
            (user_id, _now_utc_iso(), "running", provider, workspace_url, _now_utc_iso()),
        )
        con.commit()
    finally:
        con.close()

    return _status_payload(True, provider, "running", workspace_url, "Workspace iniciado (placeholder).")


@router.post("/workspace/stop")
def workspace_stop(req: Request):
    auth = _require_auth(req)
    user_id = int(auth["user"]["id"])

    enabled = _workspace_enabled()
    provider = _workspace_provider()

    con = _connect()
    try:
        _ensure_workspace_schema(con)

        row = con.execute(
            "SELECT id, workspace_url, provider FROM workspace_sessions WHERE user_id=? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()

        if not row:
            if not enabled:
                return _status_payload(False, None, "disabled", None, "Workspace ainda não configurado (Caminho A em implementação).")
            return _status_payload(True, provider, "stopped", None, "Nenhuma sessão para parar.")

        con.execute(
            "UPDATE workspace_sessions SET status=?, last_seen_utc=? WHERE id=?",
            ("stopped", _now_utc_iso(), int(row["id"])),
        )
        con.commit()

        if not enabled:
            return _status_payload(False, None, "disabled", row["workspace_url"], "Workspace ainda não configurado (Caminho A em implementação).")

        return _status_payload(True, row["provider"] or provider, "stopped", row["workspace_url"], "Workspace parado.")
    finally:
        con.close()
