# -*- coding: utf-8 -*-
# from services.zenvia import format_local_aproximado

import os
import ssl
import smtplib
import sqlite3
import secrets
import hashlib
import hmac
import base64
import json
import time
import re
import socket
import requests
import urllib3.util.connection as urllib3_cn
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Optional, Dict, Any, List, Tuple
from email.utils import formataddr

from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# HTTP "manual"
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest, urlopen
from urllib.error import URLError, HTTPError

import html as _html
from string import Template
import logging

# ---------------------------------------------------------
# Logs + .env (carregar .env da raiz ANTES de ler variáveis)
# ---------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("anjo_da_guarda.telegram")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", ".env"))
load_dotenv(ENV_PATH, override=True)   # .env do projeto
load_dotenv(override=True)             # fallback

# ---------------------------------------------------------
# Constantes / Config
# ---------------------------------------------------------
DATA_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "data"))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "anjo.db")

class CFG:
    # App
    app_title: str = "Anjo da Guarda (Web)"
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

    # E-mail
    email_enabled: bool = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
    smtp_host: str = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    smtp_user: str = os.getenv("EMAIL_USERNAME", "")
    smtp_pass: str = os.getenv("EMAIL_PASSWORD", "")
    # remetente real (fallback para EMAIL_USERNAME)
    email_from: str = os.getenv("EMAIL_FROM", "") or os.getenv("EMAIL_USERNAME", "")
    email_from_name: str = os.getenv("EMAIL_FROM_NAME", "")
    email_to_legacy: str = os.getenv("EMAIL_TO_LIST", "")

    # Telegram
    tg_enabled: bool = os.getenv("TELEGRAM_ENABLED", "true").lower() == "true"
    tg_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_bot_username: str = os.getenv("TELEGRAM_BOT_USERNAME", "")  # sem @
    tg_chat_id_legacy: str = os.getenv("TELEGRAM_CHAT_ID", "")
    tg_chat_ids: str = os.getenv("TELEGRAM_CHAT_IDS", "")
    tg_broadcast_throttle_ms: int = int(os.getenv("TELEGRAM_THROTTLE_MS", "120"))

# ---------------------------------------------------------
# App + CORS
# ---------------------------------------------------------
app = FastAPI(title=CFG.app_title)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# -----------------------------------------------------------
# Força IPv4 para evitar bloqueio do Cloudflare (IPv6 estava sendo barrado)
# -----------------------------------------------------------
def _force_ipv4():
    try:
        urllib3_cn.allowed_gai_family = lambda: socket.AF_INET
    except Exception:
        pass
_force_ipv4()

# ---------------------------------------------------------
# Helpers diversos
# ---------------------------------------------------------
def _now() -> str:
    return datetime.utcnow().isoformat()

def _valid_coords(lat: Optional[float], lon: Optional[float]) -> bool:
    try:
        if lat is None or lon is None:
            return False
        return (-90.0 <= float(lat) <= 90.0) and (-180.0 <= float(lon) <= 180.0)
    except Exception:
        return False

def _coords_str(lat: float, lon: float) -> Tuple[str, str]:
    # força ponto decimal e até 7 casas
    return (f"{float(lat):.7f}", f"{float(lon):.7f}")

def _maps_url(lat: float, lon: float) -> str:
    # padrão comprovado que funcionou
    lat_s, lon_s = _coords_str(lat, lon)
    return f"https://maps.google.com/?q={lat_s},{lon_s}"

# Gera exatamente "?q=LAT,LON" para o campo local_aproximado do template
def _local_aproximado_fragment(lat: float, lon: float) -> str:
    lat_s, lon_s = _coords_str(float(lat), float(lon))
    return f"?q={lat_s},{lon_s}"


# ---------------------------------------------------------
# DB helpers (SQLite)
# ---------------------------------------------------------
def db() -> sqlite3.Connection:
    # check_same_thread=False evita erros se você usar a conexão em tasks/threads
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def db_init():
    with db() as con:
        con.executescript("""
        PRAGMA foreign_keys=ON;

        ----------------------------------------------------------------------
        -- DLR de WhatsApp (status de entrega)
        ----------------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS wa_dlr (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT,
            to_number TEXT,
            status TEXT,
            code TEXT,
            description TEXT,
            channel TEXT,
            raw_json TEXT NOT NULL,
            received_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_wa_dlr_msg ON wa_dlr(message_id);
        CREATE INDEX IF NOT EXISTS idx_wa_dlr_received ON wa_dlr(received_at);

        ----------------------------------------------------------------------
        -- USERS & EMAIL VERIFICATION
        ----------------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            pwd_hash TEXT NOT NULL,
            pwd_salt TEXT NOT NULL,
            email_verified INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS email_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token TEXT UNIQUE NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS consents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            consent_at TEXT NOT NULL,
            ip TEXT
        );

        ----------------------------------------------------------------------
        -- PROFILE (dados cadastrais — agora com campos opcionais p/ métricas)
        ----------------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            full_name TEXT,
            cpf TEXT,
            address TEXT,
            gender TEXT,
            birthdate TEXT,
            created_at TEXT NOT NULL
        );

        ----------------------------------------------------------------------
        -- MÉTRICAS (eventos de uso p/ analytics)
        ----------------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS metrics_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_type TEXT NOT NULL,
            channel TEXT,
            lat REAL,
            lon REAL,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_metrics_created_at ON metrics_events(created_at);
        CREATE INDEX IF NOT EXISTS idx_metrics_event_type ON metrics_events(event_type);
        CREATE INDEX IF NOT EXISTS idx_metrics_channel ON metrics_events(channel);
        CREATE INDEX IF NOT EXISTS idx_metrics_user ON metrics_events(user_id);

        ----------------------------------------------------------------------
        -- CONTATOS (onde ficam destinos de notificação)
        ----------------------------------------------------------------------
        -- contacts.type em ('email','sms','whatsapp','telegram')
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type TEXT NOT NULL,
            value TEXT NOT NULL,
            is_primary INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_contacts_user ON contacts(user_id);
        CREATE INDEX IF NOT EXISTS idx_contacts_type ON contacts(type);

        CREATE TABLE IF NOT EXISTS telegram_contacts (
            contact_id INTEGER PRIMARY KEY REFERENCES contacts(id) ON DELETE CASCADE,
            activation_token TEXT UNIQUE,
            chat_id TEXT,
            activated_at TEXT
        );

        ----------------------------------------------------------------------
        -- AUDITORIA DE DISPAROS (para conferência/forense)
        ----------------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS sos_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            payload_json TEXT,
            sent_email INTEGER,
            sent_sms INTEGER,
            sent_whatsapp INTEGER,
            sent_telegram INTEGER,
            created_at TEXT NOT NULL
        );

        ----------------------------------------------------------------------
        -- DLR de SMS (status de entrega)
        ----------------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS sms_dlr (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT,
            to_number TEXT,
            status TEXT,
            code TEXT,
            description TEXT,
            raw_json TEXT NOT NULL,
            received_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sms_dlr_msg ON sms_dlr(message_id);
        CREATE INDEX IF NOT EXISTS idx_sms_dlr_received ON sms_dlr(received_at);

        ----------------------------------------------------------------------
        -- SESSÕES DE LIVE LOCATION (um registro por chat)
        ----------------------------------------------------------------------
        CREATE TABLE IF NOT EXISTS live_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_token TEXT UNIQUE NOT NULL,
            chat_id TEXT NOT NULL,
            message_id INTEGER,
            inline_message_id TEXT,
            active INTEGER DEFAULT 1,
            started_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_live_chat ON live_sessions(chat_id);
        CREATE INDEX IF NOT EXISTS idx_live_active ON live_sessions(active);
        """)

        # Migrações idempotentes (já presentes)
        try:
            con.execute("ALTER TABLE profiles ADD COLUMN gender TEXT")
        except Exception:
            pass
        try:
            con.execute("ALTER TABLE profiles ADD COLUMN birthdate TEXT")
        except Exception:
            pass

db_init()

# --------------------------- MIGRATIONS (email opcional) --------------------
def migrate_users_email_nullable():
    """
    Torna users.email opcional (remove NOT NULL) mantendo UNIQUE.
    Reconstrói a tabela somente se necessário.
    """
    with db() as con:
        con.row_factory = sqlite3.Row
        cols = list(con.execute("PRAGMA table_info(users)"))
        email_col = next((c for c in cols if c["name"] == "email"), None)
        if not email_col:
            return
        if int(email_col["notnull"]) == 1:
            con.execute("PRAGMA foreign_keys=OFF;")
            con.executescript("""
                CREATE TABLE IF NOT EXISTS users_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE,
                    pwd_hash TEXT NOT NULL,
                    pwd_salt TEXT NOT NULL,
                    email_verified INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );
                INSERT INTO users_new (id,email,pwd_hash,pwd_salt,email_verified,created_at)
                SELECT id,email,pwd_hash,pwd_salt,email_verified,created_at FROM users;
                DROP TABLE users;
                ALTER TABLE users_new RENAME TO users;
            """)
            con.execute("PRAGMA foreign_keys=ON;")

def create_optional_indexes():
    with db() as con:
        con.executescript("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_user_type_value
                ON contacts(user_id, type, value);
        """)

migrate_users_email_nullable()
create_optional_indexes()
# ---------------------------------------------------------------------------

# ---------------------------------------------------------
# Utils: password hash + tokens
# ---------------------------------------------------------
def _hash_password(pwd: str, salt: Optional[bytes] = None) -> (str, str):
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt, 120000)
    return base64.b64encode(dk).decode(), base64.b64encode(salt).decode()

def _verify_password(pwd: str, b64hash: str, b64salt: str) -> bool:
    salt = base64.b64decode(b64salt)
    dk2, _ = _hash_password(pwd, salt)
    return hmac.compare_digest(dk2, b64hash)

# ---------------------------------------------------------
# Templates Telegram (externo com fallback)
# ---------------------------------------------------------
TEMPLATES_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "templates"))
TG_SOS_TEMPLATE_PATH = os.path.join(TEMPLATES_DIR, "tg_sos.html")
_DEFAULT_TG_SOS = "<b>🚨 SOS – ANJO DA GUARDA</b>\n$TEXT_LINE\n$MAPS_LINE"
try:
    with open(TG_SOS_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        _TG_SOS_TEMPLATE = Template(f.read())
except FileNotFoundError:
    _TG_SOS_TEMPLATE = Template(_DEFAULT_TG_SOS)

def render_tg_sos_html(user_text: Optional[str], maps_link: Optional[str]) -> str:
    text_line = _html.escape(user_text) if user_text else ""
    maps_line = _html.escape(maps_link) if maps_link else ""
    return _TG_SOS_TEMPLATE.safe_substitute(TEXT_LINE=text_line, MAPS_LINE=maps_line).strip()

# ---------------------------------------------------------
# Helpers WA: limpeza de MSISDN + envio 1-a-1
# ---------------------------------------------------------
def _msisdn_clean(s: str) -> str:
    # Zenvia exige DDI+DDD+número sem '+', espaços ou sinais
    digits = re.sub(r'\D', '', s or '')
    if digits.startswith('55') and len(digits) >= 12:
        return digits
    if len(digits) >= 10 and not digits.startswith('55'):
        digits = '55' + digits
    return digits

def _wa_headers_and_proxy():
    token = os.getenv("ZENVIA_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("WA_NO_TOKEN")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-API-Token": token,
        "User-Agent": "curl/8.4.0",
    }
    proxy = os.getenv("ZENVIA_HTTP_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    proxies = {"http": proxy, "https": proxy} if proxy else None
    return headers, proxies

def send_wa_zenvia_once(_from: str, to: str, text: str) -> dict:
    import urllib3.util.connection as urllib3_cn
    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET  # força IPv4

    url = "https://api.zenvia.com/v2/channels/whatsapp/messages"
    payload = {"from": _from, "to": to, "contents": [{"type": "text", "text": text[:700]}]}
    cb = (os.getenv("ZENVIA_WA_CALLBACK_URL") or os.getenv("ZENVIA_CALLBACK_URL") or "").strip()
    if cb:
        payload["callbackUrl"] = cb

    headers, proxies = _wa_headers_and_proxy()
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20, proxies=proxies)
        ok = 200 <= resp.status_code < 300
        raw = resp.text
        logger.info("[WA] TEXT to=%s status=%s ok=%s resp=%s", to, resp.status_code, ok, raw)
        return {"ok": ok, "status": resp.status_code, "response": raw, "to": to}
    except Exception as e:
        logger.error("[WA] TEXT EXC to=%s %s", to, e)
        return {"ok": False, "reason": str(e), "to": to}

def send_wa_template_zenvia_once(_from: str, to: str, template_id: str, fields: Dict[str, Any]) -> dict:
    import urllib3.util.connection as urllib3_cn
    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET  # força IPv4

    if not template_id:
        raise RuntimeError("WA_NO_TEMPLATE_ID")

    url = "https://api.zenvia.com/v2/channels/whatsapp/messages"

    # sanitiza campos (evita None e garante string)
    f = {k: ("" if v is None else str(v)) for k, v in (fields or {}).items()}

    payload = {
        "from": _from,
        "to": _msisdn_clean(to),
        "contents": [{
            "type": "template",
            "templateId": template_id,
            "fields": f
        }]
    }
    cb = (os.getenv("ZENVIA_WA_CALLBACK_URL") or os.getenv("ZENVIA_CALLBACK_URL") or "").strip()
    if cb:
        payload["callbackUrl"] = cb

    headers, proxies = _wa_headers_and_proxy()

    # IMPORTANTE: logar depois de montar o payload
    logger.warning("[WA DEBUG PAYLOAD] %s", json.dumps(payload, ensure_ascii=False))

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20, proxies=proxies)
        ok = 200 <= resp.status_code < 300
        raw = resp.text
        logger.info("[WA] TPL  to=%s status=%s ok=%s resp=%s", to, resp.status_code, ok, raw)
        return {"ok": ok, "status": resp.status_code, "response": raw, "to": to}
    except Exception as e:
        logger.error("[WA] TPL  EXC to=%s %s", to, e)
        return {"ok": False, "reason": str(e), "to": to}

def send_wa_to_numbers(numbers: List[str], text: str, tpl_fields: Optional[Dict[str, Any]] = None) -> List[dict]:
    """Envio 1-a-1 para a lista de números do usuário (contatos pessoais)."""
    from_alias = (os.getenv("ZENVIA_WA_FROM") or os.getenv("ZENVIA_WHATSAPP_FROM") or "").strip()
    if not from_alias:
        return [{"ok": False, "reason": "WA_FROM_MISSING"}]
    template_id = (os.getenv("ZENVIA_WA_TEMPLATE_ID") or "").strip()
    use_simple = os.getenv("ZENVIA_WA_SIMPLE", "false").lower() in ("1","true","yes","on")
    logger.warning("[WA CHOICE] use_simple=%s template_id=%s tpl_fields=%s", use_simple, template_id, json.dumps(tpl_fields, ensure_ascii=False))
    results = []
    for raw in numbers:
        to = _msisdn_clean(raw)
        if not use_simple and template_id and tpl_fields:
            r = send_wa_template_zenvia_once(from_alias, to, template_id, tpl_fields)
        else:
            r = send_wa_zenvia_once(from_alias, to, (text or "")[:700])
        results.append(r)
    return results

# ---------------------------------------------------------
# E-mail
# ---------------------------------------------------------
def send_email(subject: str, body: str, to_list: Optional[List[str]] = None) -> Dict[str, Any]:
    if not CFG.email_enabled:
        return {"ok": False, "reason": "EMAIL_DISABLED"}

    to_list = to_list or ([x.strip() for x in CFG.email_to_legacy.split(",") if x.strip()])
    if not to_list:
        return {"ok": False, "reason": "EMAIL_NO_RECIPIENTS"}

    msg = EmailMessage()
    from_name = (os.getenv("EMAIL_FROM_NAME") or "").strip()
    msg["From"] = formataddr((from_name, CFG.email_from)) if from_name else CFG.email_from
    msg["To"] = ", ".join(to_list)
    msg["Subject"] = subject
    msg.set_content(body)

    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP(CFG.smtp_host, CFG.smtp_port, timeout=25) as s:
            s.ehlo(); s.starttls(context=ctx); s.ehlo()
            s.login(CFG.smtp_user, CFG.smtp_pass)
            s.send_message(msg)
        logger.info("[EMAIL] OK via STARTTLS to=%s", to_list)
        return {"ok": True}
    except Exception as e1:
        logger.warning("[EMAIL] STARTTLS falhou (%s); tentando SSL:465 ...", e1)
        try:
            with smtplib.SMTP_SSL(CFG.smtp_host, 465, context=ctx, timeout=25) as s:
                s.login(CFG.smtp_user, CFG.smtp_pass)
                s.send_message(msg)
            logger.info("[EMAIL] OK via SSL465 to=%s", to_list)
            return {"ok": True, "fallback": "SSL465"}
        except Exception as e2:
            logger.error("[EMAIL] FALHA DEFINITIVA: %s", e2)
            return {"ok": False, "reason": f"{type(e2).__name__}: {e2}"}

# ---------------------------------------------------------
# Zenvia (SMS) - legado/env
# ---------------------------------------------------------
def _resolve_sms_sender() -> str:
    return (os.getenv("ZENVIA_SMS_FROM") or os.getenv("ZENVIA_FROM") or "glaucusmotta").strip()

def send_sms_zenvia_once(_from: str, to: str, text: str) -> dict:
    import urllib3.util.connection as urllib3_cn
    urllib3_cn.allowed_gai_family = lambda: socket.AF_INET  # força IPv4

    token = os.getenv("ZENVIA_API_TOKEN", "").strip()
    if not token:
        logger.error("[SMS] NO_TOKEN")
        return {"ok": False, "reason": "NO_TOKEN", "to": to}

    url = "https://api.zenvia.com/v2/channels/sms/messages"
    payload = {"from": _from, "to": to, "contents": [{"type": "text", "text": text[:700]}]}
    cb = (os.getenv("ZENVIA_CALLBACK_URL") or "").strip()
    if cb:
        payload["callbackUrl"] = cb

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-API-Token": token,
        "User-Agent": "curl/8.4.0",
    }

    proxy = os.getenv("ZENVIA_HTTP_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    proxies = {"http": proxy, "https": proxy} if proxy else None

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20, proxies=proxies)
        ok = 200 <= resp.status_code < 300
        raw = resp.text

        if resp.status_code == 403 and "Attention Required" in raw:
            m = re.search(r"Ray ID:\s*<strong[^>]*>([^<]+)</strong>", raw)
            ray = m.group(1) if m else None
            logger.error("[SMS] CLOUDFLARE_WAF_BLOCK to=%s ray=%s", to, ray)
            return {"ok": False, "status": 403, "reason": "CLOUDFLARE_WAF_BLOCK", "ray_id": ray, "to": to}

        logger.info("[SMS] to=%s status=%s ok=%s resp=%s", to, resp.status_code, ok, raw)
        return {"ok": ok, "status": resp.status_code, "response": raw, "to": to}
    except Exception as e:
        logger.error("[SMS] EXC to=%s %s", to, e)
        return {"ok": False, "reason": str(e), "to": to}

def send_sms_zenvia_list(text: str) -> list:
    from_alias = _resolve_sms_sender()
    to_list = [x.strip() for x in os.getenv("ZENVIA_SMS_TO_LIST", "").split(",") if x.strip()]
    results = []
    for to_raw in to_list:
        results.append(send_sms_zenvia_once(from_alias, _msisdn_clean(to_raw), text))
    return results

# ---------------------------------------------------------
# Zenvia (WhatsApp) - legado/env (listas do .env)
# ---------------------------------------------------------
def send_wa_zenvia_list(text: str) -> list:
    from_alias = (os.getenv("ZENVIA_WA_FROM") or os.getenv("ZENVIA_WHATSAPP_FROM") or "").strip()
    to_raw = (os.getenv("ZENVIA_WA_TO_LIST") or os.getenv("ZENVIA_WHATSAPP_TO_LIST") or "").strip()
    to_list = [x.strip() for x in to_raw.split(",") if x.strip()]
    results = []
    for to in to_list:
        results.append(send_wa_zenvia_once(from_alias, _msisdn_clean(to), text))
    return results

def send_wa_zenvia_list_template(fields: Dict[str, Any]) -> list:
    from_alias = (os.getenv("ZENVIA_WA_FROM") or os.getenv("ZENVIA_WHATSAPP_FROM") or "").strip()
    to_raw = (os.getenv("ZENVIA_WA_TO_LIST") or os.getenv("ZENVIA_WHATSAPP_TO_LIST") or "").strip()
    template_id = (os.getenv("ZENVIA_WA_TEMPLATE_ID") or "").strip()
    to_list = [x.strip() for x in to_raw.split(",") if x.strip()]
    results = []
    for to in to_list:
        results.append(send_wa_template_zenvia_once(from_alias, _msisdn_clean(to), template_id, fields))
    return results

# ---------------------------------------------------------
# Telegram helpers
# ---------------------------------------------------------
def _parse_chat_ids_from_env() -> List[str]:
    raw = (CFG.tg_chat_ids or "").strip()
    tokens: List[str] = []
    if raw:
        tokens = [t.strip() for t in re.split(r"[,\s;]+", raw) if t.strip()]
    elif CFG.tg_chat_id_legacy:
        tokens = [CFG.tg_chat_id_legacy.strip()]

    valid: List[str] = []
    for t in tokens:
        if t.startswith("@"):
            valid.append(t); continue
        try:
            int(t); valid.append(t)
        except ValueError:
            logger.error("[TG] chat_id inválido ignorado: %r", t)
    return valid

def _send_telegram_once(chat_id: str, text: str, reply_markup: Optional[Dict[str, Any]] = None,
                        parse_mode: Optional[str] = "HTML") -> Dict[str, Any]:
    if not CFG.tg_enabled:
        return {"ok": False, "reason": "TELEGRAM_DISABLED", "chat_id": chat_id}
    if not CFG.tg_token:
        return {"ok": False, "reason": "TELEGRAM_MISSING_TOKEN", "chat_id": chat_id}

    txt = (text or "").strip()
    if not txt:
        return {"ok": False, "reason": "TEXT_EMPTY", "chat_id": chat_id}

    url = f"https://api.telegram.org/bot{CFG.tg_token}/sendMessage"
    payload: Dict[str, Any] = {"chat_id": chat_id, "text": txt[:4096], "disable_web_page_preview": True}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)

    data = urlencode(payload).encode("utf-8")
    req = UrlRequest(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", "ignore")
            logger.info("[TG] OK chat=%s %s", chat_id, raw)
            return {"ok": True, "status": resp.status, "response": raw, "chat_id": chat_id}
    except HTTPError as e:
        raw = e.read().decode("utf-8", "ignore") if e.fp else ""
        logger.error("[TG] HTTP %s chat=%s %s", e.code, chat_id, raw)
        return {"ok": False, "reason": f"HTTP {e.code}", "response": raw, "chat_id": chat_id}
    except URLError as e:
        logger.error("[TG] URLERROR chat=%s %s", chat_id, getattr(e, "reason", str(e)))
        return {"ok": False, "reason": f"URLERROR {getattr(e, 'reason', str(e))}", "chat_id": chat_id}
    except Exception as e:
        logger.error("[TG] EXC chat=%s %s", chat_id, e)
        return {"ok": False, "reason": str(e), "chat_id": chat_id}

def _send_telegram_location_once(chat_id: str, lat: float, lon: float) -> Dict[str, Any]:
    if not CFG.tg_enabled:
        return {"ok": False, "reason": "TELEGRAM_DISABLED", "chat_id": chat_id}
    if not CFG.tg_token:
        return {"ok": False, "reason": "TELEGRAM_MISSING_TOKEN", "chat_id": chat_id}

    url = f"https://api.telegram.org/bot{CFG.tg_token}/sendLocation"
    payload = {"chat_id": chat_id, "latitude": str(lat), "longitude": str(lon)}
    data = urlencode(payload).encode("utf-8")
    req = UrlRequest(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", "ignore")
            logger.info("[TG] LOC OK chat=%s %s", chat_id, raw)
            return {"ok": True, "status": resp.status, "response": raw, "chat_id": chat_id}
    except HTTPError as e:
        raw = e.read().decode("utf-8", "ignore") if e.fp else ""
        logger.error("[TG] LOC HTTP %s chat=%s %s", e.code, chat_id, raw)
        return {"ok": False, "reason": f"HTTP {e.code}", "response": raw, "chat_id": chat_id}
    except URLError as e:
        logger.error("[TG] LOC URLERROR chat=%s %s", chat_id, getattr(e, "reason", str(e)))
        return {"ok": False, "reason": f"URLERROR {getattr(e, 'reason', str(e))}", "chat_id": chat_id}
    except Exception as e:
        logger.error("[TG] LOC EXC chat=%s %s", chat_id, e)
        return {"ok": False, "reason": str(e), "chat_id": chat_id}

# -------------------------------------------------------
#  Telegram: Live Location
# -------------------------------------------------------
def _send_telegram_live_start_once(chat_id: str, lat: float, lon: float, live_period: int = 900):
    if not CFG.tg_enabled or not CFG.tg_token:
        return {"ok": False, "reason": "TELEGRAM_DISABLED_OR_NO_TOKEN", "chat_id": chat_id}
    url = f"https://api.telegram.org/bot{CFG.tg_token}/sendLocation"
    payload = {
        "chat_id": chat_id,
        "latitude": str(lat),
        "longitude": str(lon),
        "live_period": str(min(max(live_period, 60), 86400)),
    }
    data = urlencode(payload).encode("utf-8")
    req = UrlRequest(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", "ignore")
            logger.info("[TG] LIVE START chat=%s %s", chat_id, raw)
            try:
                j = json.loads(raw)
                mid = j.get("result", {}).get("message_id")
            except Exception:
                mid = None
            return {"ok": True, "status": resp.status, "response": raw, "chat_id": chat_id, "message_id": mid}
    except HTTPError as e:
        raw = e.read().decode("utf-8", "ignore") if e.fp else ""
        logger.error("[TG] LIVE START HTTP %s chat=%s %s", e.code, chat_id, raw)
        return {"ok": False, "reason": f"HTTP {e.code}", "response": raw, "chat_id": chat_id}
    except Exception as e:
        logger.error("[TG] LIVE START EXC chat=%s %s", chat_id, e)
        return {"ok": False, "reason": str(e), "chat_id": chat_id}

def _edit_telegram_live_once(chat_id: str, message_id: int, lat: float, lon: float):
    if not CFG.tg_enabled or not CFG.tg_token:
        return {"ok": False, "reason": "TELEGRAM_DISABLED_OR_NO_TOKEN", "chat_id": chat_id}
    url = f"https://api.telegram.org/bot{CFG.tg_token}/editMessageLiveLocation"
    payload = {
        "chat_id": chat_id,
        "message_id": str(message_id),
        "latitude": str(lat),
        "longitude": str(lon),
    }
    data = urlencode(payload).encode("utf-8")
    req = UrlRequest(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", "ignore")
            logger.info("[TG] LIVE EDIT chat=%s msg=%s %s", chat_id, message_id, raw)
            return {"ok": True, "status": resp.status, "response": raw, "chat_id": chat_id}
    except HTTPError as e:
        raw = e.read().decode("utf-8", "ignore") if e.fp else ""
        logger.error("[TG] LIVE EDIT HTTP %s chat=%s msg=%s %s", e.code, chat_id, message_id, raw)
        return {"ok": False, "reason": f"HTTP {e.code}", "response": raw, "chat_id": chat_id}
    except Exception as e:
        logger.error("[TG] LIVE EDIT EXC chat=%s msg=%s %s", chat_id, e)
        return {"ok": False, "reason": str(e), "chat_id": chat_id}

def _stop_telegram_live_once(chat_id: str, message_id: int):
    if not CFG.tg_enabled or not CFG.tg_token:
        return {"ok": False, "reason": "TELEGRAM_DISABLED_OR_NO_TOKEN", "chat_id": chat_id}
    url = f"https://api.telegram.org/bot{CFG.tg_token}/stopMessageLiveLocation"
    payload = {"chat_id": chat_id, "message_id": str(message_id)}
    data = urlencode(payload).encode("utf-8")
    req = UrlRequest(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", "ignore")
            logger.info("[TG] LIVE STOP chat=%s msg=%s %s", chat_id, message_id, raw)
            return {"ok": True, "status": resp.status, "response": raw, "chat_id": chat_id}
    except HTTPError as e:
        raw = e.read().decode("utf-8", "ignore") if e.fp else ""
        logger.error("[TG] LIVE STOP HTTP %s chat=%s msg=%s %s", e.code, chat_id, message_id, raw)
        return {"ok": False, "reason": f"HTTP {e.code}", "response": raw, "chat_id": chat_id}
    except Exception as e:
        logger.error("[TG] LIVE STOP EXC chat=%s msg=%s %s", chat_id, e)
        return {"ok": False, "reason": str(e), "chat_id": chat_id}

# ---------------------------------------------------------
# MODELOS
# ---------------------------------------------------------
class SosIn(BaseModel):
    lat: Optional[float] = None
    lon: Optional[float] = None
    acc: Optional[float] = None          # mantido para e-mail/Telegram; NÃO vai no template
    text: Optional[str] = None
    s1: Optional[str] = None             # pode carregar 'nome' se quiser
    s2: Optional[str] = None
    user_email: Optional[str] = None     # se vier, usa contatos do usuário

class RegisterIn(BaseModel):
    email: Optional[str] = None          # agora OPCIONAL
    password: str

class ProfileIn(BaseModel):
    token: str
    full_name: str
    cpf: str
    address: str

class ContactsIn(BaseModel):
    token: str
    emails: List[str] = []
    sms: List[str] = []
    whatsapp: List[str] = []
    telegram: List[str] = []  # OPCIONAL

# Live models
class LiveStartIn(BaseModel):
    lat: float
    lon: float
    duration: int = 900
    user_email: Optional[str] = None

class LiveUpdateIn(BaseModel):
    live_id: str
    lat: float
    lon: float

class LiveStopIn(BaseModel):
    live_id: str

# ---------------------------------------------------------
# AUTH: registro + confirmação por e-mail + termos LGPD
# ---------------------------------------------------------
@app.post("/auth/register")
def auth_register(payload: RegisterIn):
    email = (payload.email or "").strip().lower()
    pwd = payload.password
    if not pwd:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "PASSWORD_EMPTY"})

    with db() as con:
        if email:
            cur = con.execute("SELECT id FROM users WHERE email=?", (email,))
            if cur.fetchone():
                return JSONResponse(status_code=400, content={"ok": False, "reason": "EMAIL_EXISTS"})

        h, salt = _hash_password(pwd)
        email_verified = 0 if email else 1

        con.execute(
            "INSERT INTO users(email,pwd_hash,pwd_salt,email_verified,created_at) VALUES(?,?,?,?,?)",
            (email if email else None, h, salt, email_verified, _now())
        )
        uid = con.execute("SELECT id FROM users ORDER BY id DESC LIMIT 1").fetchone()["id"]

        if email:
            token = secrets.token_urlsafe(20)
            expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()
            con.execute("INSERT INTO email_tokens(user_id, token, created_at, expires_at) VALUES(?,?,?,?)",
                        (uid, token, _now(), expires))
            confirm_link = f"{CFG.public_base_url}/auth/confirm?token={token}"

            subject = "Confirme seu cadastro – Anjo da Guarda"
            body = f"""Olá!

Recebemos um pedido de cadastro no Anjo da Guarda para {email}.
Clique para confirmar: {confirm_link}

O link expira em 24 horas.

Se não foi você, ignore este e-mail.
"""
            send_email(subject, body, [email])

    return {"ok": True, "email_verification": "sent" if email else "skipped"}

@app.get("/auth/confirm")
def auth_confirm(token: str):
    html = f"""
    <html><body style="font-family:Arial;max-width:720px;margin:40px auto;">
    <h2>Termos e Consentimento (LGPD)</h2>
    <p>Para continuar, é necessário ler e concordar com os termos de ciência e autorização,
    incluindo o uso de dados pessoais para fins de contato em emergências.</p>
    <form method="post" action="/auth/consent">
      <input type="hidden" name="token" value="{_html.escape(token)}"/>
      <label><input type="checkbox" name="agree" value="on" required> Li e concordo com os termos.</label><br><br>
      <button type="submit">Concordar e continuar</button>
    </form>
    </body></html>
    """
    return HTMLResponse(content=html)

@app.post("/auth/consent")
def auth_consent(token: str = Form(...), agree: Optional[str] = Form(None), request: Request = None):
    if agree != "on":
        return HTMLResponse("<h3>Você precisa concordar para continuar.</h3>", status_code=400)

    with db() as con:
        row = con.execute("SELECT user_id, used, expires_at FROM email_tokens WHERE token=?", (token,)).fetchone()
        if not row:
            return HTMLResponse("<h3>Token inválido.</h3>", status_code=400)
        if row["used"]:
            return HTMLResponse("<h3>Token já utilizado.</h3>", status_code=400)
        if datetime.utcnow() > datetime.fromisoformat(row["expires_at"]):
            return HTMLResponse("<h3>Token expirado.</h3>", status_code=400)

        uid = row["user_id"]
        con.execute("UPDATE users SET email_verified=1 WHERE id=?", (uid,))
        con.execute("UPDATE email_tokens SET used=1 WHERE token=?", (token,))
        ip = request.client.host if request and request.client else None
        con.execute("INSERT INTO consents(user_id, consent_at, ip) VALUES(?,?,?)", (uid, _now(), ip))

    return RedirectResponse(url=f"/onboarding/profile?token={token}", status_code=302)

@app.get("/debug/zenvia_conf")
def debug_zenvia_conf():
    to_list = [x.strip() for x in (os.getenv("ZENVIA_WA_TO_LIST") or "").split(",") if x.strip()]
    return {
        "wa_from": os.getenv("ZENVIA_WA_FROM", ""),
        "wa_to_list": to_list,
        "template_id": os.getenv("ZENVIA_WA_TEMPLATE_ID", ""),
        "simple": os.getenv("ZENVIA_WA_SIMPLE", "false"),
        "callback": os.getenv("ZENVIA_CALLBACK_URL", ""),
        "token_set": bool(os.getenv("ZENVIA_API_TOKEN", "").strip()),
    }


# ---------------------------------------------------------
# Perfil
# ---------------------------------------------------------
@app.get("/onboarding/profile")
def profile_form(token: str):
    html = f"""
    <html><body style="font-family:Arial;max-width:720px;margin:40px auto;">
    <h2>Cadastro de Perfil</h2>
    <form method="post" action="/onboarding/profile">
      <input type="hidden" name="token" value="{_html.escape(token)}"/>
      <label>Nome completo:<br><input name="full_name" required></label><br><br>
      <label>CPF:<br><input name="cpf" required></label><br><br>
      <label>Endereço:<br><input name="address" required></label><br><br>
      <button type="submit">Salvar e continuar</button>
    </form>
    </body></html>
    """
    return HTMLResponse(html)

@app.post("/onboarding/profile")
def profile_save(token: str = Form(...), full_name: str = Form(...), cpf: str = Form(...), address: str = Form(...)):
    with db() as con:
        row = con.execute("SELECT user_id FROM email_tokens WHERE token=? AND used=1", (token,)).fetchone()
        if not row:
            return HTMLResponse("<h3>Token inválido.</h3>", status_code=400)
        uid = row["user_id"]
        existing = con.execute("SELECT id FROM profiles WHERE user_id=?", (uid,)).fetchone()
        if existing:
            con.execute("UPDATE profiles SET full_name=?, cpf=?, address=? WHERE user_id=?",
                        (full_name, cpf, address, uid))
        else:
            con.execute("INSERT INTO profiles(user_id, full_name, cpf, address, created_at) VALUES(?,?,?,?,?)",
                        (uid, full_name, cpf, address, _now()))

    return RedirectResponse(url=f"/onboarding/contacts?token={token}", status_code=302)

# ---------------------------------------------------------
# Contatos
# ---------------------------------------------------------
@app.get("/onboarding/contacts")
def contacts_form(token: str):
    html = f"""
    <html><body style="font-family:Arial;max-width:820px;margin:40px auto;">
    <h2>Contatos para Alerta (SOS)</h2>
    <p>Informe até 3 por tipo. Mínimo exigido: <b>1 SMS</b> e <b>1 WhatsApp</b>.
    <br>E-mail é <b>opcional</b>; Telegram também é <b>opcional</b>.</p>
    <form method="post" action="/onboarding/contacts">
      <input type="hidden" name="token" value="{_html.escape(token)}"/>

      <h3>E-mail</h3>
      <input name="emails" placeholder="email1@exemplo.com"><br>
      <input name="emails" placeholder="email2@exemplo.com"><br>
      <input name="emails" placeholder="email3@exemplo.com"><br><br>

      <h3>SMS (telefone com DDI + DDD)</h3>
      <input name="sms" placeholder="+55 11 9XXXX-XXXX"><br>
      <input name="sms" placeholder="+55 11 9XXXX-XXXX"><br>
      <input name="sms" placeholder="+55 11 9XXXX-XXXX"><br><br>

      <h3>WhatsApp (telefone com DDI + DDD)</h3>
      <input name="whatsapp" placeholder="+55 11 9XXXX-XXXX"><br>
      <input name="whatsapp" placeholder="+55 11 9XXXX-XXXX"><br>
      <input name="whatsapp" placeholder="+55 11 9XXXX-XXXX"><br><br>

      <h3>Telegram (opcional)</h3>
      <input name="telegram" placeholder="Nome do contato (opcional)"><br>
      <input name="telegram" placeholder="Nome do contato (opcional)"><br>
      <input name="telegram" placeholder="Nome do contato (opcional)"><br><br>

      <button type="submit">Salvar contatos</button>
    </form>
    </body></html>
    """
    return HTMLResponse(html)

@app.post("/onboarding/contacts")
async def contacts_save(request: Request):
    form = await request.form()
    token = form.get("token")
    emails = [v.strip() for v in form.getlist("emails") if v and v.strip()]
    sms = [v.strip() for v in form.getlist("sms") if v and v.strip()]
    whatsapp = [v.strip() for v in form.getlist("whatsapp") if v and v.strip()]
    telegram = [v.strip() for v in form.getlist("telegram") if v and v.strip()]

    if not token:
        return HTMLResponse("<h3>Token ausente.</h3>", status_code=400)
    if len(sms) < 1 or len(whatsapp) < 1:
        return HTMLResponse("<h3>Preencha ao menos 1 SMS e 1 WhatsApp (e-mail é opcional).</h3>", status_code=400)

    with db() as con:
        row = con.execute("SELECT user_id FROM email_tokens WHERE token=? AND used=1", (token,)).fetchone()
        if not row:
            return HTMLResponse("<h3>Token inválido.</h3>", status_code=400)
        uid = row["user_id"]

        con.execute("DELETE FROM contacts WHERE user_id=?", (uid,))

        def add_contacts(lst, ctype):
            for i, v in enumerate(lst[:3]):
                con.execute(
                    "INSERT INTO contacts(user_id, type, value, is_primary, status, created_at) VALUES(?,?,?,?,?,?)",
                    (uid, ctype, v, 1 if i == 0 else 0, "pending", _now())
                )

        add_contacts(emails, "email")
        add_contacts(sms, "sms")
        add_contacts(whatsapp, "whatsapp")

        tg_links = []
        if telegram:
            for i, label in enumerate(telegram[:3]):
                con.execute(
                    "INSERT INTO contacts(user_id, type, value, is_primary, status, created_at) VALUES(?,?,?,?,?,?)",
                    (uid, "telegram", label or f"telegram_{i+1}", 1 if i == 0 else 0, "pending", _now())
                )
                cid = con.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
                act = secrets.token_urlsafe(16)
                con.execute("INSERT INTO telegram_contacts(contact_id, activation_token) VALUES(?,?)", (cid, act))
                if CFG.tg_bot_username:
                    tg_link = f"https://t.me/{CFG.tg_bot_username}?start={act}"
                else:
                    tg_link = f"https://t.me/<SEU_BOT>?start={act}"
                tg_links.append((label or f"Contato {i+1}", tg_link))

    li = "".join([f'<li>{_html.escape(name)}: <a href="{_html.escape(url)}" target="_blank">{_html.escape(url)}</a></li>'
                  for name, url in tg_links]) or "<li>(Nenhum contato de Telegram cadastrado)</li>"

    html = f"""
    <html><body style="font-family:Arial;max-width:820px;margin:40px auto;">
    <h2>Contatos salvos!</h2>
    <p>Compartilhe estes <b>links de ativação do Telegram</b> (opcionais) com seus contatos:</p>
    <ul>{li}</ul>
    <hr>
    <h3>Próximo passo: Senha de voz (2 passos)</h3>
    <p>Abra o app e siga as instruções para gravar a senha de voz em 2 passos.</p>
    </body></html>
    """
    return HTMLResponse(html)

# ---------------------------------------------------------
# Webhook do Telegram (captura /start <token>)
# ---------------------------------------------------------
@app.post("/webhooks/telegram")
async def telegram_webhook(update: Dict[str, Any], bg: BackgroundTasks):
    msg = update.get("message") or update.get("edited_message") or {}
    text = (msg.get("text") or "").strip()
    chat = msg.get("chat") or {}
    chat_id = str(chat.get("id", ""))

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        token = parts[1] if len(parts) > 1 else None
        if token:
            with db() as con:
                row = con.execute("""
                    SELECT c.id AS contact_id, c.user_id
                    FROM telegram_contacts tc
                    JOIN contacts c ON c.id = tc.contact_id
                    WHERE tc.activation_token=? AND c.type='telegram'
                """, (token,)).fetchone()
                if row:
                    con.execute("UPDATE telegram_contacts SET chat_id=?, activated_at=? WHERE contact_id=?",
                                (chat_id, _now(), row["contact_id"]))
                    con.execute("UPDATE contacts SET status='active' WHERE id=?", (row["contact_id"],))
                    bg.add_task(_send_telegram_once, chat_id,
                                "<b>Notificações ativadas!</b>\nVocê passará a receber alertas SOS deste aplicativo.",
                                None, "HTML")
        else:
            _send_telegram_once(chat_id,
                                "Olá! Para ativar, toque no link de convite enviado pelo aplicativo.",
                                None, None)
    return {"ok": True}

# ---------------------------------------------------------
# Webhook Zenvia (DLR) — grava SMS em sms_dlr e WA em wa_dlr
# ---------------------------------------------------------
@app.post("/webhooks/zenvia")
async def zenvia_webhook(request: Request):
    """
    Aceita callbacks da Zenvia (SMS/WhatsApp), em dict OU lista de dicts.
    Grava SMS em sms_dlr e WhatsApp em wa_dlr.
    """
    try:
        raw_bytes = await request.body()
        raw_str = raw_bytes.decode("utf-8", "ignore")
        logger.info("[ZENVIA WH] %s", raw_str)

        try:
            payload = json.loads(raw_str)
        except Exception:
            payload = None

        # Normaliza em lista de eventos
        if isinstance(payload, dict):
            events = [payload]
        elif isinstance(payload, list):
            events = payload
        else:
            events = []

        # Atalho: ping manual
        if len(events) == 1 and isinstance(events[0], dict) and events[0].get("ping") == "ok":
            msg_id = events[0].get("messageId") or f"ping-{secrets.token_hex(4)}"
            with db() as con:
                con.execute("""
                    INSERT INTO sms_dlr (message_id, to_number, status, code, description, raw_json, received_at)
                    VALUES (?,?,?,?,?,?,?)
                """, (msg_id, "", "PING", "PING", "PING", raw_str, _now()))
            return JSONResponse({"ok": True})

        # Persiste cada evento
        with db() as con:
            for ev in events:
                if not isinstance(ev, dict):
                    continue

                # message node (alguns eventos vêm aninhados)
                msg_node = ev.get("message") or {}

                # --- Message ID robusto ---
                msg_id = (
                    (ev.get("messageId") or ev.get("id") or "") or
                    (msg_node.get("messageId") or msg_node.get("id") or "")
                )
                msg_id = str(msg_id).strip()

                # --- Canal robusto ---
                channel = (
                    (ev.get("channel") or ev.get("type") or "") or
                    (msg_node.get("channel") or msg_node.get("type") or "") or
                    (isinstance(ev.get("to"), dict) and ev.get("to", {}).get("type") or "")
                )
                channel = str(channel).strip().lower()

                # --- TO robusto (dict/str + aliases) ---
                def _extract_to(obj: dict) -> str:
                    to_raw = obj.get("to") or obj.get("destination") or obj.get("recipient")
                    if isinstance(to_raw, dict):
                        return str(
                            to_raw.get("phoneNumber") or to_raw.get("id") or to_raw.get("number") or ""
                        ).strip()
                    return str(to_raw or "").strip()

                to_number = _extract_to(ev) or _extract_to(msg_node)

                # --- STATUS robusto (dict ou string) ---
                st = ev.get("status") or ev.get("messageStatus") or ev.get("event") or ev.get("state")
                code = description = status = ""
                if isinstance(st, dict):
                    code = str(
                        st.get("code") or st.get("status") or st.get("event") or st.get("state") or ""
                    ).strip()
                    description = str(
                        st.get("description") or st.get("reason") or st.get("detail") or ""
                    ).strip()
                    status = code or "UNKNOWN"
                elif isinstance(st, str):
                    status = code = description = st.strip()
                else:
                    status = "UNKNOWN"

                # Decide a tabela pelo canal
                if channel == "whatsapp":
                    con.execute("""
                        INSERT INTO wa_dlr (message_id, to_number, status, code, description, channel, raw_json, received_at)
                        VALUES (?,?,?,?,?,?,?,?)
                    """, (msg_id, to_number, status, code, description, channel, raw_str, _now()))
                else:
                    # default -> SMS
                    con.execute("""
                        INSERT INTO sms_dlr (message_id, to_number, status, code, description, raw_json, received_at)
                        VALUES (?,?,?,?,?,?,?)
                    """, (msg_id, to_number, status, code, description, raw_str, _now()))

        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error("[ZENVIA WH][DB] %s", e)
        # mantemos 200 para Zenvia não re-tentar indefinidamente
        return JSONResponse(status_code=200, content={"ok": True})


# ---------------------------------------------------------
# Endpoints de saúde
# ---------------------------------------------------------
@app.get("/ping")
def ping():
    return {"pong": True}

@app.get("/api/health")
def health():
    return {"ok": True, "ts": _now()}

# ---------------------------------------------------------
# SOS — envia para contatos do usuário (se informado) ou listas do .env (legado)
# ---------------------------------------------------------
def _contacts_for_user(uid: int) -> Dict[str, List[sqlite3.Row]]:
    with db() as con:
        rows = con.execute(
            "SELECT * FROM contacts WHERE user_id=? AND status IN ('pending','active')",
            (uid,),
        ).fetchall()
    out = {"email": [], "sms": [], "whatsapp": [], "telegram": []}
    for r in rows:
        out[r["type"]].append(r)
    return out

def _resolve_nome_for_template(user_id: Optional[int], payload: SosIn) -> Optional[str]:
    # prioridade: env -> perfil -> payload.s1
    env_nome = (os.getenv("ZENVIA_WA_NOME") or "").strip()
    if env_nome:
        return env_nome
    if user_id:
        with db() as con:
            r = con.execute("SELECT full_name FROM profiles WHERE user_id=?", (user_id,)).fetchone()
        if r and (r["full_name"] or "").strip():
            return r["full_name"].strip()
    if payload.s1 and payload.s1.strip():
        return payload.s1.strip()
    return None

@app.post("/api/sos")
async def api_sos(payload: SosIn):
    lat, lon, acc = payload.lat, payload.lon, payload.acc

    # Monta bloco de localização
    loc_lines, maps_link = [], ""
    if _valid_coords(lat, lon):
        maps_link = _maps_url(float(lat), float(lon))
        acc_txt = f" (±{int(acc)}m)" if isinstance(acc, (int, float)) else ""
        loc_lines.append(f"Localização: lat={float(lat):.5f} lon={float(lon):.5f}{acc_txt}")
        loc_lines.append(maps_link)
    else:
        loc_lines.append("Localização: não informada")

    # E-mail
    subject = "SOS – ANJO DA GUARDA"
    body_lines = ["Alerta de emergência (ANJO DA GUARDA)", ""]
    if payload.text:
        body_lines.append(payload.text)
        body_lines.append("")
    body_lines.extend(loc_lines)
    body = "\n".join(body_lines)

    # Telegram
    tg_text = render_tg_sos_html(payload.text, maps_link)
    reply_markup = {"inline_keyboard": [[{"text": "Abrir no Maps", "url": maps_link}]]} if maps_link else None

    # Descobre user_id (se veio user_email verificado)
    user_id = None
    if payload.user_email:
        with db() as con:
            row = con.execute("SELECT id, email_verified FROM users WHERE email=?",
                              (payload.user_email.strip().lower(),)).fetchone()
            if row and row["email_verified"]:
                user_id = row["id"]

    sent_email = sent_sms = sent_whatsapp = sent_telegram = 0
    sms_results: List[Dict[str, Any]] = []
    wa_results: List[Dict[str, Any]] = []

    # Nome para template (se existir)
    nome_tpl = _resolve_nome_for_template(user_id, payload)

    if user_id:
        # Fan-out por usuário (contatos pessoais)
        contacts = _contacts_for_user(user_id)

        # E-mail dos contatos
        if contacts["email"]:
            email_list = [c["value"] for c in contacts["email"]]
            r = send_email(subject, body, email_list)
            logger.info("[EMAIL] result=%s", r)
            sent_email = 1 if r.get("ok") else 0

        # WhatsApp por contatos do usuário (transacional, 1-a-1)
        wa_numbers = [c["value"] for c in contacts["whatsapp"]]
        if wa_numbers:
            use_simple_wa = os.getenv("ZENVIA_WA_SIMPLE", "false").lower() in ("1", "true", "yes", "on")
            template_id = (os.getenv("ZENVIA_WA_TEMPLATE_ID") or "").strip()
            fields_mode = (os.getenv("ZENVIA_WA_FIELDS_MODE", "latlon") or "latlon").lower()  # "maps" ou "latlon"
            nome_tpl = (os.getenv("ZENVIA_WA_NOME") or (payload.s1 or "")).strip()

            if use_simple_wa or not template_id:
                # modo texto simples (fora da janela 24h pode rejeitar)
                wa_text = f"SOS - {maps_link or ''}".strip()
                tpl_fields = None
            else:
                # modo template aprovado
                wa_text = ""  # não usado em template
                tpl_fields = {}
                if nome_tpl:
                    tpl_fields["nome"] = nome_tpl

                if fields_mode == "maps":
                    # template com variáveis {{nome}} e {{maps_link}}
                    if maps_link:
                        tpl_fields["local_aproximado"] = _local_aproximado_fragment(float(lat), float(lon))
                else:
                    # template com variáveis {{nome}}, {{lat}} e {{lon}}
                    if lat is not None:
                        tpl_fields["lat"] = str(lat)
                    if lon is not None:
                        tpl_fields["lon"] = str(lon)

        wa_user_results = send_wa_to_numbers(wa_numbers, wa_text, tpl_fields)
        wa_results.extend(wa_user_results)
        logger.info("[WA][USER] results=%s", wa_user_results)
        sent_whatsapp = 1 if any(r.get("ok") for r in wa_user_results) else 0


        # (Opcional futuro) SMS por contatos do usuário
        if contacts["sms"]:
            # TODO: implementar envio SMS por contato (mantido para fase seguinte)
            sent_sms = sent_sms or 0

        # Telegram por contatos (ativados)
        if contacts["telegram"] and CFG.tg_enabled:
            with db() as con:
                rows = con.execute("""
                    SELECT tc.chat_id FROM telegram_contacts tc
                    JOIN contacts c ON c.id = tc.contact_id
                    WHERE c.user_id=? AND c.type='telegram' AND c.status='active' AND tc.chat_id IS NOT NULL
                """, (user_id,)).fetchall()
            res_all = []
            any_ok = False
            for i, rr in enumerate(rows):
                cid = rr["chat_id"]
                res_all.append(_send_telegram_once(cid, tg_text, reply_markup, "HTML"))
                any_ok = any_ok or res_all[-1].get("ok", False)
                if CFG.tg_broadcast_throttle_ms and i < len(rows) - 1:
                    time.sleep(CFG.tg_broadcast_throttle_ms / 1000.0)
            if any_ok and _valid_coords(lat, lon):
                for i, rr in enumerate(rows):
                    _send_telegram_location_once(rr["chat_id"], float(lat), float(lon))
                    if CFG.tg_broadcast_throttle_ms and i < len(rows) - 1:
                        time.sleep(CFG.tg_broadcast_throttle_ms / 1000.0)
            sent_telegram = 1 if any_ok else 0
        else:
            sent_telegram = 0

    else:
        # LEGADO: usa as listas do .env
        r = send_email(subject, body, None)
        sent_email = 1 if r.get("ok") else 0

        # SMS (Zenvia) – legado via .env
        try:
            token_ok = bool(os.getenv("ZENVIA_API_TOKEN"))
            to_raw = os.getenv("ZENVIA_SMS_TO_LIST", "")
            if token_ok and to_raw:
                use_simple = os.getenv("ZENVIA_SMS_SIMPLE", "false").lower() in ("1", "true", "yes", "on")
                if use_simple:
                    sms_text = f"SOS - {maps_link or ''}".strip()
                else:
                    sms_text = f"🚨 SOS – ANJO DA GUARDA\n{(payload.text or '').strip()}\n{maps_link or ''}".strip()

                override = (os.getenv("ZENVIA_SMS_TEST") or "").strip()
                if override:
                    try:
                        sms_text = override.format(
                            maps_link=maps_link or "",
                            MAPS_LINK=maps_link or "",
                            text=(payload.text or "").strip(),
                            TEXT=(payload.text or "").strip(),
                        )
                    except Exception as e:
                        logger.warning("[SMS] override.format falhou: %s; usando fallback literal", e)
                        sms_text = (override
                                    .replace("{maps_link}", maps_link or "")
                                    .replace("{MAPS_LINK}", maps_link or "")
                                    .replace("{text}", (payload.text or "").strip())
                                    .replace("{TEXT}", (payload.text or "").strip()))
                sms_text = sms_text.replace("\\n", "\n").replace("\\r\\n", "\n")[:700]

                logger.info("[SMS] sending... from=%s to_list=%s", _resolve_sms_sender(), to_raw)
                sms_results = send_sms_zenvia_list(sms_text)
                sent_sms = 1 if any(r.get("ok") for r in sms_results) else 0
                logger.info("[SMS] results=%s", sms_results)
            else:
                logger.info("[SMS] skipped: token_ok=%s to_list_present=%s", token_ok, bool(to_raw))
        except Exception as e:
            logger.error("[SMS] erro ao enviar: %s", e)

        # WhatsApp (Zenvia) – legado via .env
        try:
            wa_enabled = (os.getenv("ZENVIA_WA_ENABLED", os.getenv("ZENVIA_WHATSAPP_ENABLED", "false")).lower()
                          in ("1", "true", "yes", "on"))
            from_wa = (os.getenv("ZENVIA_WA_FROM") or os.getenv("ZENVIA_WHATSAPP_FROM") or "").strip()
            to_wa_raw = (os.getenv("ZENVIA_WA_TO_LIST") or os.getenv("ZENVIA_WHATSAPP_TO_LIST") or "").strip()
            template_id = (os.getenv("ZENVIA_WA_TEMPLATE_ID") or "").strip()

            if wa_enabled and from_wa and to_wa_raw:
                use_simple_wa = os.getenv("ZENVIA_WA_SIMPLE", "false").lower() in ("1","true","yes","on")

                if use_simple_wa or not template_id:
                    wa_text = f"🚨 SOS – ANJO DA GUARDA\n{(payload.text or '').strip()}\n{maps_link or ''}".strip()
                    tpl_fields = None
                else:
                    tpl_fields = {}
                    if _valid_coords(lat, lon) and maps_link:
                        tpl_fields["local_aproximado"] = _local_aproximado_fragment(float(lat), float(lon))
                    if nome_tpl:
                        tpl_fields["nome"] = nome_tpl
                    wa_text = ""

                logger.info("[WA] sending... from=%s to_list=%s mode=%s",
                            from_wa, to_wa_raw,
                            "template" if (not use_simple_wa and template_id) else "text")
                wa_fallback_text = ("🚨 SOS – ANJO DA GUARDA" + (f"\n{maps_link}" if maps_link else "")).strip()


                if not use_simple_wa and template_id:
                    try:
                        wa_results = send_wa_zenvia_list_template(tpl_fields)
                    except Exception as e_tpl:
                        logger.warning("[WA] template falhou (%s); usando texto", e_tpl)
                        wa_results = send_wa_zenvia_list(wa_fallback_text)
                else:
                    wa_results = send_wa_zenvia_list(wa_fallback_text)

                sent_whatsapp = 1 if any(r.get("ok") for r in wa_results) else 0
                logger.info("[WA] results=%s", wa_results)
            else:
                logger.info("[WA] skipped: enabled=%s from=%s to_list_present=%s",
                            wa_enabled, bool(from_wa), bool(to_wa_raw))
        except Exception as e:
            logger.error("[WA] erro ao enviar: %s", e)

        # Telegram (legado por .env)
        any_ok = False
        if CFG.tg_enabled and (CFG.tg_chat_ids or CFG.tg_chat_id_legacy):
            chat_ids = _parse_chat_ids_from_env()
            for i, cid in enumerate(chat_ids):
                res = _send_telegram_once(cid, tg_text, reply_markup, "HTML")
                any_ok = any_ok or res.get("ok", False)
                if CFG.tg_broadcast_throttle_ms and i < len(chat_ids) - 1:
                    time.sleep(CFG.tg_broadcast_throttle_ms / 1000.0)
            if any_ok and _valid_coords(lat, lon):
                for i, cid in enumerate(chat_ids):
                    _send_telegram_location_once(cid, float(lat), float(lon))
                    if CFG.tg_broadcast_throttle_ms and i < len(chat_ids) - 1:
                        time.sleep(CFG.tg_broadcast_throttle_ms / 1000.0)
        sent_telegram = 1 if any_ok else 0

    # Auditoria
    with db() as con:
        con.execute("""
            INSERT INTO sos_audit(user_id, payload_json, sent_email, sent_sms, sent_whatsapp, sent_telegram, created_at)
            VALUES(?,?,?,?,?,?,?)
        """, (user_id, json.dumps(payload.dict()), sent_email, sent_sms, sent_whatsapp, sent_telegram, _now()))

    ok = any([sent_email, sent_sms, sent_whatsapp, sent_telegram])
    return JSONResponse(
        status_code=200 if ok else 500,
        content={
            "ok": ok,
            "status": {
                "email": sent_email,
                "sms": sent_sms,
                "whatsapp": sent_whatsapp,
                "telegram": sent_telegram,
                "sms_results": sms_results,
                "wa_results": wa_results,
            }
        }
    )

# ---------------------------------------------------------
# Live Location (start / update / stop)
# ---------------------------------------------------------
def _live_destinations_for(user_email: Optional[str]):
    user_id = None
    chat_ids: List[str] = []
    if user_email:
        with db() as con:
            row = con.execute("SELECT id, email_verified FROM users WHERE email=?",
                              (user_email.strip().lower(),)).fetchone()
            if row and row["email_verified"]:
                user_id = row["id"]
                rows = con.execute("""
                    SELECT tc.chat_id FROM telegram_contacts tc
                    JOIN contacts c ON c.id = tc.contact_id
                    WHERE c.user_id=? AND c.type='telegram' AND c.status='active' AND tc.chat_id IS NOT NULL
                """, (user_id,)).fetchall()
                chat_ids = [r["chat_id"] for r in rows]
    if not chat_ids:
        chat_ids = _parse_chat_ids_from_env()
    return user_id, chat_ids

@app.post("/api/live/start")
def live_start(payload: LiveStartIn):
    if not CFG.tg_enabled:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "TELEGRAM_DISABLED"})
    user_id, chat_ids = _live_destinations_for(payload.user_email)
    if not chat_ids:
        return JSONResponse(status_code=400, content={"ok": False, "reason": "NO_CHAT_IDS"})

    live_id = secrets.token_urlsafe(10)
    expires = (datetime.utcnow() + timedelta(seconds=min(max(payload.duration, 60), 86400))).isoformat()

    results = []
    any_ok = False
    for cid in chat_ids:
        r = _send_telegram_live_start_once(cid, float(payload.lat), float(payload.lon), payload.duration)
        results.append(r)
        mid = r.get("message_id")

        if r.get("ok") and mid:
            try:
                with db() as con:
                    con.execute("""
                        INSERT INTO live_sessions
                          (user_id, session_token, chat_id, message_id, active, started_at, expires_at)
                        VALUES (?,?,?,?,1,?,?)
                    """, (user_id, live_id, str(cid), int(mid), _now(), expires))
                logger.info("[DB] LIVE SAVED token=%s chat_id=%s msg_id=%s expires=%s",
                            live_id, cid, mid, expires)
                any_ok = True
            except Exception as e:
                logger.error("[DB] LIVE INSERT ERROR token=%s chat_id=%s msg_id=%s err=%s",
                             live_id, cid, mid, e)
                results.append({"ok": False, "reason": f"DB_ERROR: {e}", "chat_id": cid})
        else:
            logger.warning("[DB] LIVE NOT SAVED token=%s chat_id=%s ok=%s msg_id=%r reason=%s",
                           live_id, cid, r.get("ok"), mid, r.get("reason") or r.get("response"))

    return JSONResponse(status_code=200 if any_ok else 500,
                        content={"ok": any_ok, "live_id": live_id, "results": results})

@app.post("/api/live/update")
def live_update(payload: LiveUpdateIn):
    with db() as con:
        rows = con.execute("""
            SELECT chat_id, message_id FROM live_sessions
            WHERE session_token=? AND active=1
        """, (payload.live_id,)).fetchall()
    if not rows:
        return JSONResponse(status_code=404, content={"ok": False, "reason": "LIVE_NOT_FOUND_OR_INACTIVE"})

    results = []
    any_ok = False
    for r in rows:
        res = _edit_telegram_live_once(str(r["chat_id"]), int(r["message_id"]), float(payload.lat), float(payload.lon))
        results.append(res)
        any_ok = any_ok or res.get("ok", False)
    return {"ok": any_ok, "results": results}

@app.post("/api/live/stop")
def live_stop(payload: LiveStopIn):
    with db() as con:
        rows = con.execute("""
            SELECT chat_id, message_id FROM live_sessions
            WHERE session_token=? AND active=1
        """, (payload.live_id,)).fetchall()
    if not rows:
        return JSONResponse(status_code=404, content={"ok": False, "reason": "LIVE_NOT_FOUND_OR_INACTIVE"})

    results = []
    any_ok = False
    for r in rows:
        res = _stop_telegram_live_once(str(r["chat_id"]), int(r["message_id"]))
        results.append(res)
        any_ok = any_ok or res.get("ok", False)

    with db() as con:
        con.execute("UPDATE live_sessions SET active=0 WHERE session_token=?", (payload.live_id,))
    return {"ok": any_ok, "results": results}

# ---------------------------------------------------------
# Debug: últimos DLRs de SMS e WA
# ---------------------------------------------------------
@app.get("/debug/sms_dlr_recent")
def debug_sms_dlr_recent(limit: int = 20):
    with db() as con:
        rows = con.execute("""
            SELECT id, message_id, to_number, status, code, description, received_at
            FROM sms_dlr
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return {"rows": [dict(r) for r in rows]}

@app.get("/debug/wa_dlr_recent")
def debug_wa_dlr_recent(limit: int = 20):
    with db() as con:
        rows = con.execute("""
            SELECT id, message_id, to_number, status, code, description, channel, received_at
            FROM wa_dlr
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return {"rows": [dict(r) for r in rows]}

# ---------------------------------------------------------
# Estáticos (deixe no fim)
# ---------------------------------------------------------
WEB_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "web"))
if not os.path.isdir(WEB_DIR):
    os.makedirs(WEB_DIR, exist_ok=True)
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

