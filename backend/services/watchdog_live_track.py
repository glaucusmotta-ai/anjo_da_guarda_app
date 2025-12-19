import os
import json
import sqlite3
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone

logger = logging.getLogger("watchdog")
logging.basicConfig(level=logging.INFO)

# ===== util: carregar .env (fallback) =====
def _load_env_from_file() -> None:
    # tenta backend/.env e raiz/.env
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
        except Exception as e:
            logger.warning("Falha ao ler .env (%s): %s", path, e)

def _getenv_any(*keys: str, default: str = "") -> str:
    for k in keys:
        v = os.getenv(k, "")
        if v:
            return v
    return default

def _parse_ts_to_utc(ts_raw: str) -> datetime | None:
    if not ts_raw:
        return None
    s = str(ts_raw).strip()
    if not s:
        return None

    # "YYYY-MM-DD HH:MM:SS" -> "YYYY-MM-DDTHH:MM:SS"
    if "T" not in s and " " in s:
        s = s.replace(" ", "T", 1)

    # corta microsegundos longos (mantém ms/µs ok)
    # (python aceita até 6, mas se vier maior, corta)
    if "." in s:
        head, tail = s.split(".", 1)
        digits = ""
        rest = ""
        for ch in tail:
            if ch.isdigit():
                digits += ch
            else:
                rest = tail[len(digits):]
                break
        if len(digits) > 6:
            digits = digits[:6]
        s = head + "." + digits + rest

    # se não tiver tz, assume UTC
    if not (s.endswith("Z") or "+" in s[-6:] or "-" in s[-6:]):
        s = s + "Z"

    # datetime.fromisoformat não aceita "Z" diretamente
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

# ===== DB do watchdog (estado/antispam) =====
def _db_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))          # backend/services
    backend_dir = os.path.normpath(os.path.join(here, ".."))   # backend
    root_dir = os.path.normpath(os.path.join(backend_dir, ".."))
    data_dir = os.path.join(root_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "anjo.db")

def _init_state_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS watchdog_state (
        session_id TEXT PRIMARY KEY,
        last_state TEXT NOT NULL,
        last_alert_utc TEXT,
        last_seen_utc TEXT
    );
    """)
    conn.commit()

def _get_state(conn: sqlite3.Connection, session_id: str) -> dict:
    row = conn.execute(
        "SELECT session_id,last_state,last_alert_utc,last_seen_utc FROM watchdog_state WHERE session_id=?",
        (session_id,),
    ).fetchone()
    if not row:
        return {"session_id": session_id, "last_state": "OK", "last_alert_utc": None, "last_seen_utc": None}
    return {"session_id": row[0], "last_state": row[1], "last_alert_utc": row[2], "last_seen_utc": row[3]}

def _set_state(conn: sqlite3.Connection, session_id: str, state: str, last_alert_utc: str | None, last_seen_utc: str | None) -> None:
    conn.execute("""
    INSERT INTO watchdog_state(session_id,last_state,last_alert_utc,last_seen_utc)
    VALUES(?,?,?,?)
    ON CONFLICT(session_id) DO UPDATE SET
        last_state=excluded.last_state,
        last_alert_utc=excluded.last_alert_utc,
        last_seen_utc=excluded.last_seen_utc
    """, (session_id, state, last_alert_utc, last_seen_utc))
    conn.commit()

# ===== Envio Telegram =====
def _send_telegram(msg: str) -> None:
    token = _getenv_any("TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN", "TG_BOT_TOKEN")
    chat_id = _getenv_any("TELEGRAM_CHAT_ID", "TELEGRAM_ADMIN_CHAT_ID", "TG_CHAT_ID")
    if not token or not chat_id:
        logger.info("[watchdog] Telegram não configurado (token/chat_id). Pulando.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": msg}).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            _ = r.read()
    except Exception as e:
        logger.warning("[watchdog] Falha Telegram: %s", e)

# ===== Envio Email (SendGrid HTTP) =====
def _send_email(msg: str, subject: str) -> None:
    api_key = _getenv_any("SENDGRID_API_KEY", "SENDGRID_KEY")
    from_email = _getenv_any("SENDGRID_FROM", "EMAIL_FROM", "MAIL_FROM")
    to_emails = _getenv_any("WATCHDOG_EMAIL_TO", "ALERT_EMAIL_TO", "ADMIN_EMAIL", "EMAIL_TO")

    if not api_key or not from_email or not to_emails:
        logger.info("[watchdog] Email (SendGrid) não configurado (API_KEY/FROM/TO). Pulando.")
        return

    tos = [e.strip() for e in to_emails.split(",") if e.strip()]
    if not tos:
        return

    url = "https://api.sendgrid.com/v3/mail/send"
    body = {
        "personalizations": [{"to": [{"email": e} for e in tos], "subject": subject}],
        "from": {"email": from_email},
        "content": [{"type": "text/plain", "value": msg}],
    }
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            _ = r.read()
    except Exception as e:
        logger.warning("[watchdog] Falha Email (SendGrid): %s", e)

def main() -> None:
    _load_env_from_file()

    base_url = _getenv_any("WATCHDOG_BASE_URL", default="http://127.0.0.1:8000").rstrip("/")
    warn_s = int(_getenv_any("WATCHDOG_WARN_SECONDS", default="60"))
    crit_s = int(_getenv_any("WATCHDOG_CRIT_SECONDS", default="180"))
    cooldown_s = int(_getenv_any("WATCHDOG_COOLDOWN_SECONDS", default="300"))  # 5 min antispam

    now = datetime.now(timezone.utc)

    # pega sessões
    try:
        with urllib.request.urlopen(f"{base_url}/api/live-track/list", timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        msg = f"[WATCHDOG] Falha ao consultar /api/live-track/list em {base_url}: {e}"
        _send_telegram(msg)
        _send_email(msg, subject="WATCHDOG - Falha consulta backend")
        return

    sessions = data.get("sessions") or []
    if not sessions:
        logger.info("[watchdog] sem sessões ativas no momento.")
        return

    conn = sqlite3.connect(_db_path())
    try:
        _init_state_table(conn)

        for s in sessions:
            session_id = s.get("id") or ""
            if not session_id:
                continue
            if s.get("active") is False:
                continue

            nome = s.get("nome") or s.get("name") or "contato"
            phone = s.get("phone") or ""
            updated_at = s.get("updated_at") or ""
            dt = _parse_ts_to_utc(updated_at)

            if not dt:
                continue

            age = int((now - dt).total_seconds())
            state = "OK"
            if age >= crit_s:
                state = "CRIT"
            elif age >= warn_s:
                state = "WARN"

            prev = _get_state(conn, session_id)
            prev_state = prev["last_state"]
            prev_alert = _parse_ts_to_utc(prev["last_alert_utc"]) if prev["last_alert_utc"] else None

            should_alert = False
            alert_kind = None

            # escalou ou entrou em WARN/CRIT
            if state in ("WARN", "CRIT") and prev_state != state:
                should_alert = True
                alert_kind = state

            # continua em WARN/CRIT, mas respeita cooldown
            if state in ("WARN", "CRIT") and prev_state == state:
                if not prev_alert or int((now - prev_alert).total_seconds()) >= cooldown_s:
                    should_alert = True
                    alert_kind = state

            # recuperou
            if state == "OK" and prev_state in ("WARN", "CRIT"):
                should_alert = True
                alert_kind = "RECOVER"

            # links
            public_url = s.get("tracking_url") or f"/t/{session_id}"

            if should_alert:
                if alert_kind == "RECOVER":
                    msg = (
                        f"✅ [WATCHDOG] Recuperou\n"
                        f"Sessão: {nome} {('— ' + phone) if phone else ''}\n"
                        f"Último update: {updated_at}\n"
                        f"Link: {public_url}"
                    )
                    subject = "WATCHDOG - Recuperou"
                else:
                    tag = "⚠️" if alert_kind == "WARN" else "🚨"
                    msg = (
                        f"{tag} [WATCHDOG] Sem atualização\n"
                        f"Sessão: {nome} {('— ' + phone) if phone else ''}\n"
                        f"Sem atualizar há: {age}s\n"
                        f"Último update: {updated_at}\n"
                        f"Link: {public_url}"
                    )
                    subject = "WATCHDOG - Atenção" if alert_kind == "WARN" else "WATCHDOG - CRÍTICO"

                _send_telegram(msg)
                _send_email(msg, subject=subject)
                _set_state(conn, session_id, state, now.isoformat(), dt.isoformat())
            else:
                _set_state(conn, session_id, state, prev["last_alert_utc"], dt.isoformat())

    finally:
        conn.close()

if __name__ == "__main__":
    main()
