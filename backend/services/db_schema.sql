PRAGMA foreign_keys=ON;

----------------------------------------------------------------------
-- DLR de WhatsApp
----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wa_dlr (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    telefone TEXT,
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
    email TEXT UNIQUE,
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
-- PROFILE
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
-- MÉTRICAS
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
-- CONTATOS
----------------------------------------------------------------------
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
-- AUDITORIA DE DISPAROS
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
-- DLR de SMS
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
-- SESSÕES DE LIVE LOCATION (Telegram live)
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
    expires_at TEXT NOT NULL,
    last_lat REAL,
    last_lon REAL,
    last_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_live_chat ON live_sessions(chat_id);
CREATE INDEX IF NOT EXISTS idx_live_active ON live_sessions(active);
