# -*- coding: utf-8 -*-
import os
import time
import json
import base64
import hmac
import hashlib
import secrets
import logging
import html as _html
from typing import Optional, Dict

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

logger = logging.getLogger("anjo_da_guarda")

COOKIE_NAME = "localiza_session"


# ----------------------------
# Helpers (env / cookie session)
# ----------------------------
def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def _now() -> int:
    return int(time.time())


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(payload_b64: str, secret: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return _b64u(mac)


def _make_cookie(email: str, secret: str, ttl_seconds: int = 8 * 60 * 60) -> str:
    obj = {
        "email": email,
        "exp": _now() + ttl_seconds,
        "nonce": secrets.token_urlsafe(8),
    }
    payload = _b64u(json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    sig = _sign(payload, secret)
    return f"{payload}.{sig}"


def _read_cookie(value: str, secret: str) -> Optional[str]:
    if not value or "." not in value:
        return None
    payload, sig = value.split(".", 1)
    expected = _sign(payload, secret)
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        obj = json.loads(_b64u_decode(payload).decode("utf-8"))
        if int(obj.get("exp", 0)) < _now():
            return None
        email = str(obj.get("email", "")).strip()
        return email or None
    except Exception:
        return None


def _is_https(request: Request) -> bool:
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return (proto or "").lower() == "https"


def _get_session_email(request: Request) -> Optional[str]:
    secret = _env("CENTRAL_LOCALIZA_SESSION_SECRET")
    if not secret:
        return None
    return _read_cookie(request.cookies.get(COOKIE_NAME, ""), secret)

def _parse_supervisors() -> Dict[str, str]:
    raw = _env("CENTRAL_LOCALIZA_SUPERVISORS", "")
    users: Dict[str, str] = {}
    for item in raw.split(";"):
        item = item.strip()
        if not item or ":" not in item:
            continue
        u, p = item.split(":", 1)
        u = u.strip()
        p = p.strip()
        if u and p:
            users[u] = p
    return users


# ----------------------------
# HTML (login / forgot / dashboard placeholder)
# ----------------------------
def _login_html(action_url: str, forgot_url: str, back_url: str, error_msg: str = "") -> str:
    # Paleta (padrão do app)
    # Fundo: #050A1A -> #0A1430 | Azul: #1B618F | Teal: #109B92 | CTA: #0BCA96
    err = ""
    if error_msg:
        err = f"<div class='err'>{_html.escape(error_msg)}</div>"

    return f"""<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Central Localiza</title>
  <style>
    :root {{
      --bgTop: #050A1A;
      --bgBot: #0A1430;

      --blue: #1B618F;
      --teal: #109B92;
      --cta:  #0BCA96;

      --cardA: rgba(27, 97, 143, 0.42);
      --cardB: rgba(18, 51, 86, 0.20);

      --group: rgba(27, 97, 143, 0.20);
      --stroke: rgba(16, 155, 146, 0.28);

      --text:  #F9F9F9;
      --muted: #718696;

      --input: rgba(0,0,0,0.35);
      --shadow: rgba(0,0,0,0.55);
    }}

    html {{ font-size: 13px; }} /* reduz fonte geral */

    body {{
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial;
      color: var(--text);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 22px 14px;

      /* mesmo “clima” do app (SettingsScreen) */
      background:
        radial-gradient(1200px 600px at 50% 18%, rgba(27,97,143,.18) 0%, rgba(5,10,26,1) 62%),
        radial-gradient(900px 500px at 70% 65%, rgba(16,155,146,.08) 0%, rgba(10,20,48,1) 65%),
        linear-gradient(180deg, var(--bgTop) 0%, var(--bgBot) 100%);
    }}

    .wrap {{
      width: min(820px, 94vw);
      text-align: center;
    }}

    h1 {{
      margin: 0 0 6px 0;
      font-weight: 800;
      letter-spacing: .2px;

      /* menor que antes */
      font-size: clamp(26px, 3.6vw, 42px);
      text-shadow: 0 10px 30px rgba(0,0,0,.55);
    }}

    .subtitle {{
      color: var(--muted);
      margin-bottom: 16px;
      font-size: 1.0rem;
    }}

    .card {{
      margin: 0 auto;
      width: min(680px, 100%);
      border-radius: 18px;
      padding: 20px;

      background: linear-gradient(180deg, var(--cardA), var(--cardB));
      border: 1px solid rgba(16,155,146,.22);

      box-shadow:
        0 0 0 1px rgba(11,202,150,.14),
        0 0 28px rgba(11,202,150,.08),
        0 22px 60px var(--shadow);

      backdrop-filter: blur(10px);
      text-align: left;
    }}

    .err {{
      background: rgba(255, 77, 77, .10);
      border: 1px solid rgba(255, 77, 77, .35);
      color: #ffd6d6;
      padding: 10px 12px;
      border-radius: 12px;
      margin-bottom: 12px;
      font-size: .95rem;
    }}

    .group {{
      background: var(--group);
      border: 1px solid rgba(16,155,146,.18);
      border-radius: 16px;
      padding: 14px;
      margin-bottom: 14px;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.06);
    }}

    label {{
      display: block;
      margin-bottom: 8px;
      color: rgba(249,249,249,.86);
      font-size: .92rem;
    }}

    input {{
      width: 100%;
      box-sizing: border-box;
      border-radius: 12px;
      height: 44px;
      padding: 10px 12px;

      border: 1px solid rgba(255,255,255,.22);
      background: var(--input);
      color: var(--text);
      outline: none;

      font-size: .95rem;
      box-shadow: 0 10px 24px rgba(0,0,0,.20);
    }}

    input::placeholder {{ color: rgba(113,134,150,.80); }}

    input:focus {{
      border-color: rgba(11,202,150,.55);
      box-shadow:
        0 0 0 2px rgba(11,202,150,.12),
        0 0 22px rgba(11,202,150,.10);
    }}

    .pw-row {{
      position: relative;
      display: flex;
      align-items: center;
    }}

    .pw-row input {{
      padding-right: 56px; /* reserva espaço pro olhinho */
    }}

    .eye {{
      position: absolute;
      right: 10px;
      top: 50%;
      transform: translateY(-50%);

      width: 40px;
      height: 40px;
      border-radius: 12px;

      border: 1px solid rgba(16,155,146,.20);
      background: rgba(0,0,0,.22);

      display: grid;
      place-items: center;
      cursor: pointer;

      box-shadow:
        0 0 0 1px rgba(11,202,150,.08),
        0 0 18px rgba(11,202,150,.06);

      user-select: none;
    }}

    .eye:hover {{
      border-color: rgba(11,202,150,.50);
      box-shadow:
        0 0 0 1px rgba(11,202,150,.18),
        0 0 24px rgba(11,202,150,.14);
    }}

    .btn {{
      width: 100%;
      border: none;
      padding: 14px 14px;
      border-radius: 16px;

      background: linear-gradient(180deg, rgba(11,202,150,1), rgba(16,155,146,1));
      color: #041017;

      font-weight: 800;
      font-size: 1.05rem;
      cursor: pointer;

      box-shadow:
        0 0 0 1px rgba(11,202,150,.28),
        0 0 28px rgba(11,202,150,.18),
        0 16px 34px rgba(0,0,0,.34);

      transition: transform .12s ease, box-shadow .12s ease;
    }}

    .btn:hover {{
      transform: translateY(-1px);
      box-shadow:
        0 0 0 1px rgba(11,202,150,.50),
        0 0 34px rgba(11,202,150,.26),
        0 18px 40px rgba(0,0,0,.40);
    }}

    .links {{
      margin-top: 12px;
      display: flex;
      justify-content: space-between;
      gap: 12px;
      font-size: .92rem;
      flex-wrap: wrap;
    }}

    a {{
      color: rgba(11,202,150,.95);
      text-decoration: none;
    }}
    a:hover {{ text-decoration: underline; }}

    @media (max-width: 520px) {{
      body {{ padding: 18px 12px; }}
      .card {{ padding: 16px; border-radius: 16px; }}
      .links {{ flex-direction: column; align-items: flex-start; }}
      h1 {{ font-size: 34px; }}
      .subtitle {{ font-size: 0.95rem; margin-bottom: 14px; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Central Localiza</h1>
    <div class="subtitle">Área restrita do supervisor.</div>

    <div class="card">
      {err}

      <form method="post" action="{action_url}" autocomplete="off">
        <div class="group">
          <label for="email">E-mail do supervisor</label>
          <input id="email" name="email" type="email" placeholder="supervisor@empresa.com" required />
        </div>

        <div class="group">
          <label for="password">Senha do supervisor</label>
          <div class="pw-row">
            <input id="password" name="password" type="password" placeholder="••••••••" required />
            <div class="eye" id="toggleEye" title="Mostrar/ocultar senha">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" stroke="rgba(249,249,249,.85)" stroke-width="2"/>
                <circle cx="12" cy="12" r="3" stroke="rgba(249,249,249,.85)" stroke-width="2"/>
              </svg>
            </div>
          </div>
        </div>

        <button class="btn" type="submit">Entrar</button>

        <div class="links">
          <a href="{forgot_url}">Esqueci minha senha</a>
          <a href="{back_url}">Voltar para Central</a>
        </div>
      </form>
    </div>
  </div>

  <script>
    (function() {{
      const eye = document.getElementById("toggleEye");
      const pw = document.getElementById("password");
      if (!eye || !pw) return;
      eye.addEventListener("click", function() {{
        pw.type = (pw.type === "password") ? "text" : "password";
      }});
    }})();
  </script>
</body>
</html>
"""


def _forgot_html(back_url: str) -> str:
    return f"""<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Esqueci minha senha</title>
  <style>
    :root {{
      --bgTop: #050A1A;
      --bgBot: #0A1430;
      --teal: #109B92;
      --cta:  #0BCA96;
      --text: #F9F9F9;
      --muted:#718696;
    }}
    body {{
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial;
      margin: 0;
      padding: 22px 14px;
      color: var(--text);
      display:flex;
      justify-content:center;

      background:
        radial-gradient(1200px 600px at 50% 18%, rgba(27,97,143,.16) 0%, rgba(5,10,26,1) 62%),
        radial-gradient(900px 500px at 70% 65%, rgba(16,155,146,.08) 0%, rgba(10,20,48,1) 65%),
        linear-gradient(180deg, var(--bgTop) 0%, var(--bgBot) 100%);
    }}
    .card {{
      width: min(680px, 100%);
      border: 1px solid rgba(16,155,146,.22);
      border-radius: 16px;
      padding: 16px;
      background: rgba(27,97,143,.18);
      box-shadow: 0 18px 50px rgba(0,0,0,.45);
    }}
    h2 {{ margin-top: 0; font-size: 1.25rem; }}
    a {{ color: var(--cta); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    p {{ color: var(--muted); line-height: 1.35; }}
  </style>
</head>
<body>
  <div class="card">
    <h2>Esqueci minha senha</h2>
    <p>Por segurança, a recuperação de senha do Localiza será feita via supervisor master / auditoria.</p>
    <p><b>Ação agora:</b> solicite ao administrador a redefinição do seu acesso.</p>
    <p><a href="{back_url}">← Voltar</a></p>
  </div>
</body>
</html>
"""


def _dashboard_html(email: str, logout_url: str, back_url: str) -> str:
    safe_email = _html.escape(email or "")
    return f"""<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Localiza</title>

  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  />

  <style>
    :root {{
      --bgTop: #050A1A;
      --bgBot: #0A1430;
      --cta:  #0BCA96;
      --text: #F9F9F9;
      --muted:#718696;
    }}

    * {{ box-sizing: border-box; }}

    html, body {{
      height: 100%;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial;
      color: var(--text);
      background:
        radial-gradient(1200px 600px at 50% 18%, rgba(27,97,143,.16) 0%, rgba(5,10,26,1) 62%),
        radial-gradient(900px 500px at 70% 65%, rgba(16,155,146,.08) 0%, rgba(10,20,48,1) 65%),
        linear-gradient(180deg, var(--bgTop) 0%, var(--bgBot) 100%);
      display: flex;
      flex-direction: column;
    }}

    a {{ color: var(--cta); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    .top {{
      padding: 14px 16px;
      border-bottom: 1px solid rgba(255,255,255,.08);
      background: rgba(0,0,0,.20);
      backdrop-filter: blur(8px);
    }}

    .top-inner {{
      max-width: 1200px;
      margin: 0 auto;
    }}

    .title {{
      font-weight: 900;
      font-size: 18px;
      letter-spacing: .2px;
    }}

    .muted {{ color: var(--muted); margin-top: 2px; }}

    #status {{
      margin-top: 8px;
      font-size: 13px;
      color: rgba(249,249,249,.85);
    }}

    /* BARRA DE AÇÕES NO MESMO PADRÃO DO /central */
    #actions {{
      margin-top: 10px;
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      font-size: 12px;
    }}

    .btn {{
      display: inline-block;
      padding: 6px 10px;
      border-radius: 4px;
      border: 1px solid #444;
      background: #222;
      color: #fff;
      cursor: pointer;
      user-select: none;
      text-decoration: none; /* garante padrão em <a> */
      font: inherit;
      line-height: 1.1;
    }}

    .btn:hover {{
      background: #333;
      border-color: rgba(11,202,150,.55);
      box-shadow: 0 0 0 2px rgba(11,202,150,.10);
    }}

    #container {{
      flex: 1 1 auto;
      display: flex;
      min-height: 0;
    }}

    #map {{
      flex: 2;
      min-height: 0;
    }}

    #sidebar {{
      flex: 1;
      max-width: 380px;
      min-width: 280px;
      border-left: 1px solid rgba(255,255,255,.08);
      background: rgba(0,0,0,.18);
      padding: 10px 12px;
      overflow-y: auto;
      min-height: 0;
    }}

    #sidebar h3 {{
      margin: 6px 0 10px;
      font-size: 14px;
    }}

    #sessions-list {{
      list-style: none;
      padding: 0;
      margin: 0;
      font-size: 13px;
    }}

    #sessions-list li {{
      padding: 8px 6px;
      border-bottom: 1px solid rgba(255,255,255,.06);
      cursor: pointer;
      border-radius: 10px;
    }}
    #sessions-list li:hover {{
      background: rgba(255,255,255,.04);
    }}

    #sessions-list small {{
      color: rgba(255,255,255,.65);
    }}

    .finder {{
      margin-top: 10px;
      padding: 10px 12px;
      border: 1px solid rgba(255,255,255,.08);
      border-radius: 12px;
      background: rgba(0,0,0,.18);
      display:flex;
      gap: 8px;
      align-items:center;
      flex-wrap: wrap;
    }}

    .finder label {{
      font-size: 12px;
      color: rgba(255,255,255,.75);
      margin-right: 4px;
    }}

    .finder input {{
      height: 30px;
      padding: 6px 8px;
      border-radius: 8px;
      border: 1px solid rgba(255,255,255,.18);
      background: rgba(0,0,0,.22);
      color: var(--text);
      outline: none;
      font-size: 13px;
      min-width: 190px;
    }}

    .finder input:focus {{
      border-color: rgba(11,202,150,.55);
      box-shadow: 0 0 0 2px rgba(11,202,150,.10);
    }}


    @media (max-width: 820px) {{
      #sidebar {{ max-width: 45vw; }}
    }}
  </style>
</head>

<body>
  <div class="top">
    <div class="top-inner">
      <div class="title">Localiza (Supervisor)</div>
      <div class="muted">Logado como: <b>{safe_email}</b></div>

      <div id="status">Carregando sessões...</div>

      <div id="actions">
        <button class="btn" id="btn-fit" type="button">Visão geral</button>
        <button class="btn" id="btn-toggle-sidebar" type="button">Ocultar lista</button>
        <a class="btn" href="{back_url}">Voltar para Central</a>
        <a class="btn" href="{logout_url}">Sair</a>
      </div>
    </div>
  </div>

  <div class="top-row">
    <div class="finder">
      <label for="client-code">Código do cliente</label>
      <input id="client-code" placeholder="ex: ios_mvp ou código informado" />

      <label for="client-phone">Celular</label>
      <input id="client-phone" placeholder="+55 11 99999-9999" />

      <span class="btn" id="btn-open-client">Abrir mapa</span>
      <span class="btn" id="btn-focus-client">Focar no mapa</span>
      <span class="btn" id="btn-clear-client">Limpar</span>
    </div>
  </div>

  <div id="container">
    <div id="map"></div>
    <div id="sidebar">
      <h3>Sessões</h3>
      <ul id="sessions-list"></ul>
    </div>
  </div>

  <script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin="">
  </script>

  <script>
    const statusEl = document.getElementById("status");
    const listEl = document.getElementById("sessions-list");
    const btnFit = document.getElementById("btn-fit");
    const sidebar = document.getElementById("sidebar");
    const btnToggleSidebar = document.getElementById("btn-toggle-sidebar");

    const inpCode = document.getElementById("client-code");
    const inpPhone = document.getElementById("client-phone");
    const btnOpenClient = document.getElementById("btn-open-client");
    const btnFocusClient = document.getElementById("btn-focus-client");
    const btnClearClient = document.getElementById("btn-clear-client");

        function getClientCode() {{
      return String((inpCode && inpCode.value) ? inpCode.value : "").trim();
    }}

    function getClientPhone() {{
      return String((inpPhone && inpPhone.value) ? inpPhone.value : "").trim();
    }}

    function normPhone(s) {{
      // normaliza: mantém só dígitos e opcional + no começo
      let t = String(s || "").trim();
      if (!t) return "";
      // mantém + no início, remove resto que não é número
      let plus = t.startsWith("+") ? "+" : "";
      t = t.replace(/[^0-9]/g, "");
      return plus + t;
    }}

    let lastSessionsRaw = [];

    function findSession(code, phone) {{
      const c = String(code || "").trim();
      const p = normPhone(phone);

      // tenta por id/session_id
      if (c) {{
        for (const s of (lastSessionsRaw || [])) {{
          const id = s.id || s.session_id || s.code || s.token;
          if (id && String(id).trim() === c) return s;
        }}
      }}

      // tenta por phone (se o backend estiver mandando "phone")
      if (p) {{
        for (const s of (lastSessionsRaw || [])) {{
          const sp = normPhone(s.phone || s.celular || s.msisdn || "");
          if (sp && sp === p) return s;
        }}
      }}

      return null;
    }}

    function ensureMarkerPopup(id) {{
      try {{
        const m = markers[id];
        if (m && m.openPopup) m.openPopup();
      }} catch (e) {{}}
    }}

    // ⚙️ IMPORTANTE: dentro do updateSessions(sessions) (no começo ou no fim),
    // garanta que ele atualiza esta variável:
    // lastSessionsRaw = (sessions || []);
    //
    // (Se você já tem updateSessions, só adicione 1 linha lá.)

    btnOpenClient.onclick = () => {{
      const code = getClientCode();
      const phone = getClientPhone();
      const s = findSession(code, phone);

      if (!s) {{
        statusEl.textContent = "Não encontrei sessão para esse código/celular.";
        return;
      }}

      const id = s.id || s.session_id || s.code || s.token;
      if (!id) {{
        statusEl.textContent = "Sessão inválida (sem id).";
        return;
      }}

      window.open("/t/" + encodeURIComponent(id), "_blank", "noopener");
    }};

    btnFocusClient.onclick = () => {{
      const code = getClientCode();
      const phone = getClientPhone();
      const s = findSession(code, phone);

      if (!s) {{
        statusEl.textContent = "Não encontrei sessão para esse código/celular.";
        return;
      }}

      const id = s.id || s.session_id || s.code || s.token;
      const lat = s.lat;
      const lon = s.lon;

      if (typeof lat !== "number" || typeof lon !== "number") {{
        statusEl.textContent = "Sessão encontrada, mas sem coordenadas válidas ainda.";
        return;
      }}

      map.setView([lat, lon], 16);
      ensureMarkerPopup(id);
      statusEl.textContent = "Focado em: " + (id || "-");
    }};

    btnClearClient.onclick = () => {{
      if (inpCode) inpCode.value = "";
      if (inpPhone) inpPhone.value = "";
      statusEl.textContent = "OK.";
    }};


    let map = L.map("map").setView([-14.2350, -51.9253], 4);
    setTimeout(() => {{ map.invalidateSize(); }}, 50);

    L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors"
    }}).addTo(map);

    function normalizeIsoTs(tsRaw) {{
      let iso = String(tsRaw || "").trim();
      if (!iso) return "";
      if (iso.indexOf("T") === -1 && iso.indexOf(" ") !== -1) iso = iso.replace(" ", "T");
      iso = iso.replace(/(\\.[0-9]{{3}})[0-9]+/, "$1");
      if (!/(Z|[+\\-][0-9]{{2}}:?[0-9]{{2}})$/i.test(iso)) iso = iso + "Z";
      return iso;
    }}

    function formatTsToLocal(tsRaw) {{
      if (!tsRaw) return "";
      try {{
        const iso = normalizeIsoTs(tsRaw);
        if (!iso) return "";
        const d = new Date(iso);
        if (isNaN(d.getTime())) return String(tsRaw);
        return d.toLocaleString("pt-BR", {{
          timeZone: "America/Sao_Paulo",
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }});
      }} catch (e) {{
        return String(tsRaw);
      }}
    }}

    function parseActive(val) {{
      if (val === true || val === 1) return true;
      const s = String(val || "").toLowerCase().trim();
      return s === "true" || s === "1" || s === "yes" || s === "on";
    }}

    const markers = {{}};
    let autoFit = true;
    let lastCoordsAll = [];

    let sidebarVisible = true;
    btnToggleSidebar.onclick = () => {{
      sidebarVisible = !sidebarVisible;
      if (sidebarVisible) {{
        sidebar.style.display = "block";
        btnToggleSidebar.textContent = "Ocultar lista";
      }} else {{
        sidebar.style.display = "none";
        btnToggleSidebar.textContent = "Mostrar lista";
      }}
      setTimeout(() => {{ map.invalidateSize(); }}, 200);
    }};

    map.on("movestart", () => {{ autoFit = false; }});
    map.on("zoomstart", () => {{ autoFit = false; }});

    function updateSessions(sessions) {{
      const seen = new Set();
      const coordsAll = [];
      listEl.innerHTML = "";
      lastSessionsRaw = (sessions || []);


      (sessions || []).forEach((s) => {{
        const id = s.id || s.session_id || s.code || s.token;
        if (!id) return;

        const lat = s.lat;
        const lon = s.lon;
        if (typeof lat !== "number" || typeof lon !== "number") return;

        seen.add(id);
        coordsAll.push([lat, lon]);

        const nome = s.nome || s.display_name || s.name || "contato";
        const phone = s.phone || "";
        const lastRaw = s.updated_at || s.ts || "";
        const lastLocal = formatTsToLocal(lastRaw);
        const active = parseActive(s.active);

        const baseStyle = active
          ? {{ radius: 8, color: "#0f0", weight: 2, fillColor: "#0f0", fillOpacity: 0.65 }}
          : {{ radius: 8, color: "#f80", weight: 2, fillColor: "#666", fillOpacity: 0.55 }};

        let marker = markers[id];
        const popupHtml =
          "<b>" + nome + "</b>" +
          (phone ? "<br/>📱 " + phone : "") +
          "<br/>⏱ " + (lastLocal || "-") +
          "<br/>" +
          (active ? "<span style='color:#0f0;'>Ativo</span>" : "<span style='color:#f80;'>Encerrado</span>") +
          "<br/><a href='/t/" + encodeURIComponent(id) + "' target='_blank' rel='noopener'>Abrir mapa detalhado</a>";

        if (!marker) {{
          marker = L.circleMarker([lat, lon], baseStyle).addTo(map);
          markers[id] = marker;
          marker.bindPopup(popupHtml);
        }} else {{
          marker.setLatLng([lat, lon]);
          marker.setStyle(baseStyle);
          try {{
            if (marker.getPopup()) marker.getPopup().setContent(popupHtml);
          }} catch (e) {{
            marker.bindPopup(popupHtml);
          }}
        }}

        const li = document.createElement("li");
        li.innerHTML =
          "<b>" + nome + "</b>" +
          (phone ? " — " + phone : "") +
          " <small>(" + (active ? "ativo" : "encerrado") + ")</small>" +
          "<br/><small>⏱ " + (lastLocal || "-") + "</small>";

        li.onclick = () => {{
          map.setView([lat, lon], 16);
          try {{ marker.openPopup(); }} catch (e) {{}}
        }};

        listEl.appendChild(li);
      }});

      Object.keys(markers).forEach((id) => {{
        if (!seen.has(id)) {{
          map.removeLayer(markers[id]);
          delete markers[id];
        }}
      }});

      lastCoordsAll = coordsAll.slice();

      if (coordsAll.length > 0) {{
        if (autoFit) {{
          const bounds = L.latLngBounds(coordsAll);
          map.fitBounds(bounds, {{ padding: [30, 30] }});
        }}
        statusEl.textContent = "Sessões: " + coordsAll.length;
      }} else {{
        statusEl.textContent = "";
      }}
    }}

    btnFit.onclick = () => {{
      if (lastCoordsAll.length > 0) {{
        const bounds = L.latLngBounds(lastCoordsAll);
        map.fitBounds(bounds, {{ padding: [30, 30] }});
      }} else {{
        map.setView([-14.2350, -51.9253], 4);
      }}
      autoFit = true;
    }};

    async function poll() {{
      try {{
        const resp = await fetch("/api/live-track/list?_=" + Date.now(), {{
          credentials: "same-origin",
          cache: "no-store",
          headers: {{ "Accept": "application/json" }}
        }});

        if (!resp.ok) {{
          statusEl.textContent = "Erro ao buscar sessões (HTTP " + resp.status + ").";
        }} else {{
          const data = await resp.json();
          updateSessions((data && data.sessions) ? data.sessions : []);
        }}
      }} catch (e) {{
        statusEl.textContent = "Erro de comunicação com o servidor.";
      }} finally {{
        setTimeout(poll, 3000);
      }}
    }}

    poll();
  </script>
</body>
</html>
"""



# ----------------------------
# Handlers (para o anjo_web_main.py mapear nas rotas)
# ----------------------------
async def central_localiza_page(request: Request) -> HTMLResponse:
    # Decide URLs pelo path (alias /central/login ou rota /central/localiza)
    path = request.url.path or ""
    if path == "/central/login":
        action = "/central/login"
        forgot = "/central/forgot"
        logout = "/central/logout"
    else:
        action = "/central/localiza/login"
        forgot = "/central/localiza/forgot"
        logout = "/central/localiza/logout"

    back = "/central/localiza/exit"  # não mexe no mapa/central; só volta pra lá

    email = _get_session_email(request)
    if email:
        return HTMLResponse(_dashboard_html(email=email, logout_url=logout, back_url=back))

    return HTMLResponse(_login_html(action_url=action, forgot_url=forgot, back_url=back))


async def central_localiza_login(request: Request) -> Response:
    # POST de login (funciona para /central/login e /central/localiza/login)
    form = await request.form()
    email = (form.get("email") or "").strip()
    password = (form.get("password") or "").strip()

    path = request.url.path or ""
    if path == "/central/login":
        action = "/central/login"
        forgot = "/central/forgot"
    else:
        action = "/central/localiza/login"
        forgot = "/central/localiza/forgot"

    back = "/central"

    # valida config (sem mostrar os nomes das vars na tela)
    allowed = _parse_supervisors()
    env_secret = _env("CENTRAL_LOCALIZA_SESSION_SECRET")

    if not allowed or not env_secret:
        logger.error("[LOCALIZA] .env incompleto: CENTRAL_LOCALIZA_SUPERVISORS ou CENTRAL_LOCALIZA_SESSION_SECRET ausente")
        return HTMLResponse(
            _login_html(
                action_url=action,
                forgot_url=forgot,
                back_url=back,
                error_msg="Configuração do sistema incompleta. Fale com o administrador.",
            ),
            status_code=500,
        )

    if not email or "@" not in email:
        return HTMLResponse(
            _login_html(
                action_url=action,
                forgot_url=forgot,
                back_url=back,
                error_msg="Informe um e-mail válido.",
            ),
            status_code=400,
        )

    expected = allowed.get(email)
    if (not expected) or (password != expected):
        logger.warning("[LOCALIZA] login FAIL email=%s ip=%s", email, (request.client.host if request.client else ""))
        return HTMLResponse(
            _login_html(
                action_url=action,
                forgot_url=forgot,
                back_url=back,
                error_msg="Credenciais inválidas.",
            ),
            status_code=401,
        )


    # OK: cria sessão
    cookie_val = _make_cookie(email=email, secret=env_secret)
    https = _is_https(request)

    logger.info("[LOCALIZA] login OK email=%s ip=%s", email, (request.client.host if request.client else ""))

    # redireciona para a tela principal (mantém o “ponto de entrada”)
    redirect_to = "/central/login" if path == "/central/login" else "/central/localiza"
    resp = RedirectResponse(url=redirect_to, status_code=303)
    resp.set_cookie(
        COOKIE_NAME,
        cookie_val,
        httponly=True,
        secure=https,  # em local (http) fica False, em produção (https) fica True
        samesite="lax",
        max_age=8 * 60 * 60,
        path="/",
    )
    return resp


async def central_localiza_logout(request: Request) -> Response:
    # limpa cookie e volta pro login (no mesmo “ponto de entrada”)
    path = request.url.path or ""
    target = "/central/login" if path == "/central/logout" else "/central/localiza"

    resp = RedirectResponse(url=target, status_code=303)
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp


async def central_localiza_forgot(request: Request) -> HTMLResponse:
    # Volta pro ponto certo
    path = request.url.path or ""
    back = "/central/login" if path == "/central/forgot" else "/central/localiza"
    return HTMLResponse(_forgot_html(back_url=back))


async def central_localiza_exit(request: Request) -> Response:
    # Sai do Localiza indo pra Central, limpando cookie (exige senha ao voltar)
    resp = RedirectResponse(url="/central", status_code=303)
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp


