# backend/services/service_mapa.py

import os
import sqlite3
import logging
from typing import List, Optional, Set, Any
from datetime import datetime, timezone

from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

# =========================================================
# PATHS / DB
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))            # backend/services
ROOT_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", ".."))  # raiz do projeto
DATA_DIR = os.path.join(ROOT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Banco único do sistema (observação: fica na raiz/data, não dentro de backend/)
DB_PATH = os.path.join(DATA_DIR, "anjo.db")

_LTP_COLS_CACHE: Optional[Set[str]] = None


def _open_conn() -> sqlite3.Connection:
    """
    Abre conexão sqlite com pragmas mais robustos para ambiente web (FastAPI).
    """
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=8000;")
        # WAL costuma reduzir 'database is locked' em cenários concorrentes
        conn.execute("PRAGMA journal_mode=WAL;")
    except Exception:
        # não falha a app se o sqlite não aceitar algum pragma
        pass
    return conn


def _clear_cols_cache() -> None:
    global _LTP_COLS_CACHE
    _LTP_COLS_CACHE = None


def _ensure_live_track_points_table(conn: sqlite3.Connection) -> None:
    """
    Garante a tabela mínima (para não quebrar o mapa).
    Se você já tem migração/upgrade, isso não atrapalha.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS live_track_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            created_at_utc TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ltp_session_time
            ON live_track_points(session_id, created_at_utc);
        """
    )
    _clear_cols_cache()


def _get_live_track_points_cols(conn: sqlite3.Connection) -> Set[str]:
    """
    Descobre (e cacheia) as colunas atuais da tabela live_track_points.
    """
    global _LTP_COLS_CACHE
    if _LTP_COLS_CACHE is not None:
        return _LTP_COLS_CACHE

    cols: Set[str] = set()
    try:
        rows = conn.execute("PRAGMA table_info(live_track_points);").fetchall()
        for r in rows:
            try:
                cols.add(str(r[1]))
            except Exception:
                pass
    except Exception:
        cols = set()

    _LTP_COLS_CACHE = cols
    return cols


def _normalize_ts(ts: Any) -> str:
    """
    Aceita ts como str ou datetime. Retorna ISO em UTC.
    """
    if ts is None:
        return datetime.now(timezone.utc).isoformat()

    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc).isoformat()

    s = str(ts).strip()
    if not s:
        return datetime.now(timezone.utc).isoformat()

    # "2025-12-16 21:44:20" -> "2025-12-16T21:44:20"
    if "T" not in s and " " in s:
        s = s.replace(" ", "T", 1)

    # tenta parsear e normalizar
    try:
        s2 = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        # mantém como veio (frontend já normaliza/assume UTC se precisar)
        return s


def _insert_point(conn: sqlite3.Connection, session_id: str, ts_value: str, lat: float, lon: float) -> None:
    cols = _get_live_track_points_cols(conn)

    # combinações possíveis (por compatibilidade com versões antigas)
    if "created_at_utc" in cols and "ts" in cols:
        conn.execute(
            """
            INSERT INTO live_track_points (
                session_id,
                created_at_utc,
                lat,
                lon,
                ts
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, ts_value, float(lat), float(lon), ts_value),
        )
        return

    if "created_at_utc" in cols and "ts" not in cols:
        conn.execute(
            """
            INSERT INTO live_track_points (
                session_id,
                created_at_utc,
                lat,
                lon
            ) VALUES (?, ?, ?, ?)
            """,
            (session_id, ts_value, float(lat), float(lon)),
        )
        return

    if "ts" in cols and "created_at_utc" not in cols:
        conn.execute(
            """
            INSERT INTO live_track_points (
                session_id,
                ts,
                lat,
                lon
            ) VALUES (?, ?, ?, ?)
            """,
            (session_id, ts_value, float(lat), float(lon)),
        )
        return

    # fallback ultra-legado
    conn.execute(
        "INSERT INTO live_track_points (session_id, lat, lon) VALUES (?, ?, ?)",
        (session_id, float(lat), float(lon)),
    )


# =========================================================
# API DE PERSISTÊNCIA (TRILHA)
# =========================================================

def salvar_ponto_trilha(*args) -> None:
    """
    Compatível com:
      A) salvar_ponto_trilha(session_id, lat, lon, ts)
      B) salvar_ponto_trilha(session_id, lat, lon)  -> ts = agora UTC
      C) salvar_ponto_trilha(conn, session_id, lat, lon, ts)
      D) salvar_ponto_trilha(conn, session_id, ts, lat, lon)  (legado)
    """
    conn: Optional[sqlite3.Connection] = None
    session_id: str = ""
    lat: float
    lon: float
    ts_value: str

    if not args:
        return

    if isinstance(args[0], sqlite3.Connection):
        conn = args[0]
        rest = list(args[1:])

        if len(rest) == 4:
            session_id = str(rest[0]).strip()

            second = rest[1]
            looks_number = False
            try:
                float(second)
                looks_number = True
            except Exception:
                looks_number = False

            if looks_number:
                lat = float(rest[1])
                lon = float(rest[2])
                ts_value = _normalize_ts(rest[3])
            else:
                ts_value = _normalize_ts(rest[1])
                lat = float(rest[2])
                lon = float(rest[3])

        elif len(rest) == 3:
            session_id = str(rest[0]).strip()
            lat = float(rest[1])
            lon = float(rest[2])
            ts_value = _normalize_ts(None)
        else:
            raise TypeError("salvar_ponto_trilha: argumentos inválidos (modo conn)")

    else:
        if len(args) == 4:
            session_id = str(args[0]).strip()
            lat = float(args[1])
            lon = float(args[2])
            ts_value = _normalize_ts(args[3])
        elif len(args) == 3:
            session_id = str(args[0]).strip()
            lat = float(args[1])
            lon = float(args[2])
            ts_value = _normalize_ts(None)
        else:
            raise TypeError("salvar_ponto_trilha: argumentos inválidos")

    if not session_id:
        return

    opened_here = False
    if conn is None:
        conn = _open_conn()
        opened_here = True

    try:
        # garante tabela mínima para não quebrar o mapa
        _ensure_live_track_points_table(conn)

        try:
            _insert_point(conn, session_id, ts_value, lat, lon)
            conn.commit()
        except sqlite3.OperationalError as e:
            # se schema mudou enquanto o serviço estava rodando, limpa cache e tenta uma vez
            _clear_cols_cache()
            if "no such table" in str(e).lower():
                _ensure_live_track_points_table(conn)
            _insert_point(conn, session_id, ts_value, lat, lon)
            conn.commit()

    except Exception as e:
        try:
            logger.error("[TRACK] erro ao salvar ponto da trilha no banco: %s", e)
        except Exception:
            print("[TRACK] erro ao salvar ponto da trilha no banco:", e)
    finally:
        if opened_here:
            try:
                conn.close()
            except Exception:
                pass


def listar_pontos_trilha(session_id: str) -> List[dict]:
    """
    Lista pontos da trilha.
    Retorna: [{session_id, lat, lon, ts}]
    """
    if not session_id:
        return []

    conn = _open_conn()
    conn.row_factory = sqlite3.Row
    try:
        cols = _get_live_track_points_cols(conn)
        if not cols:
            # tabela pode não existir ainda
            return []

        if "created_at_utc" in cols and "ts" in cols:
            sql = """
                SELECT
                    session_id,
                    lat,
                    lon,
                    COALESCE(ts, created_at_utc) AS ts_value
                FROM live_track_points
                WHERE session_id = ?
                ORDER BY created_at_utc ASC
            """
        elif "created_at_utc" in cols:
            sql = """
                SELECT
                    session_id,
                    lat,
                    lon,
                    created_at_utc AS ts_value
                FROM live_track_points
                WHERE session_id = ?
                ORDER BY created_at_utc ASC
            """
        elif "ts" in cols:
            sql = """
                SELECT
                    session_id,
                    lat,
                    lon,
                    ts AS ts_value
                FROM live_track_points
                WHERE session_id = ?
                ORDER BY ts ASC
            """
        else:
            sql = """
                SELECT
                    session_id,
                    lat,
                    lon,
                    '' AS ts_value
                FROM live_track_points
                WHERE session_id = ?
            """

        rows = conn.execute(sql, (session_id,)).fetchall()

        pontos: List[dict] = []
        for r in rows:
            pontos.append(
                {
                    "session_id": r["session_id"],
                    "lat": r["lat"],
                    "lon": r["lon"],
                    "ts": r["ts_value"],
                }
            )
        return pontos

    except Exception as e:
        try:
            logger.error("[TRACK] erro ao listar pontos da trilha: %s", e)
        except Exception:
            print("[TRACK] erro ao listar pontos da trilha:", e)
        return []
    finally:
        try:
            conn.close()
        except Exception:
            pass


# =========================================================
# HTML DA CENTRAL (/central)
# =========================================================

def central_page() -> HTMLResponse:
    """
    Central:
      - mapa + lista de sessões
      - atualiza a cada 3s via /api/live-track/list
      - permite encerrar via DELETE /api/live-track/session/{id}
    """
    html = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
      <meta charset="utf-8">
      <title>Central - Anjo da Guarda</title>
      <meta name="viewport" content="width=device-width, initial-scale=1"/>

      <link
        rel="stylesheet"
        href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
        integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
        crossorigin=""
      />

      <style>
        * { box-sizing: border-box; }
        html, body {
          height: 100%;
          margin: 0;
          padding: 0;
        }
        body {
          display: flex;
          flex-direction: column;
          font-family: Arial, sans-serif;
          background: #000;
          color: #fff;
        }
        #topbar {
          background: #111;
          padding: 10px 16px;
          font-size: 14px;
          line-height: 1.4;
          border-bottom: 1px solid #333;
          flex: 0 0 auto;
        }
        #title { font-weight: bold; }
        #status { font-size: 12px; opacity: 0.8; }
        #actions { margin-top: 4px; font-size: 12px; }
        .btn {
          display: inline-block;
          padding: 4px 8px;
          margin-right: 6px;
          border-radius: 3px;
          border: 1px solid #444;
          background: #222;
          color: #fff;
          cursor: pointer;
          user-select: none;
        }
        .btn:hover { background: #333; }
        #container {
          flex: 1 1 auto;
          display: flex;
          min-height: 0;
          height: 100%;
        }
        #map { flex: 2; min-height: 0; }
        #sidebar {
          flex: 1;
          max-width: 360px;
          background: #111;
          border-left: 1px solid #333;
          padding: 8px 12px;
          overflow-y: auto;
          min-height: 0;
        }
        #sidebar h3 { margin-top: 4px; margin-bottom: 8px; font-size: 14px; }
        #sessions-list {
          list-style: none;
          padding: 0;
          margin: 0;
          font-size: 13px;
        }
        #sessions-list li {
          padding: 6px 4px;
          border-bottom: 1px solid #222;
          cursor: pointer;
        }
        #sessions-list li:hover { background: #222; }
        #sessions-list small { color: #aaa; }
        #sessions-list a.encerrar {
          color: #f66;
          font-size: 11px;
          margin-left: 6px;
          text-decoration: none;
        }
        #sessions-list a.encerrar:hover { text-decoration: underline; }

        @media (max-width: 768px) {
          #sidebar { max-width: 45vw; }
        }
      </style>
    </head>
    <body>
      <div id="topbar">
        <div id="title">🚨 Central - Anjo da Guarda</div>
        <div id="status">Carregando sessões...</div>
        <div id="actions">
          <span class="btn" id="btn-fit">Visão geral</span>
          <span class="btn" id="btn-toggle-sidebar">Ocultar lista</span>
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

        let map = L.map("map").setView([-14.2350, -51.9253], 4);

        // Ajuste: invalida size depois que o mapa existe (especialmente em mobile)
        setTimeout(() => { map.invalidateSize(); }, 50);

        function normalizeIsoTs(tsRaw) {
          let iso = String(tsRaw || "").trim();
          if (!iso) return "";

          // "2025-12-16 21:44:20" -> "2025-12-16T21:44:20"
          if (iso.indexOf("T") === -1 && iso.indexOf(" ") !== -1) {
            iso = iso.replace(" ", "T");
          }

          // corta microssegundos para milissegundos: .593255 -> .593
          iso = iso.replace(/(\\.[0-9]{3})[0-9]+/, "$1");

          // se não terminar com Z ou offset, assume UTC e adiciona Z
          if (!/(Z|[+\\-][0-9]{2}:?[0-9]{2})$/i.test(iso)) {
            iso = iso + "Z";
          }
          return iso;
        }

        function formatTsToLocal(tsRaw) {
          if (!tsRaw) return "";
          try {
            const iso = normalizeIsoTs(tsRaw);
            if (!iso) return "";

            const d = new Date(iso);
            if (isNaN(d.getTime())) {
              return String(tsRaw);
            }

            return d.toLocaleString("pt-BR", {
              timeZone: "America/Sao_Paulo",
              year: "numeric",
              month: "2-digit",
              day: "2-digit",
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            });
          } catch (e) {
            console.error("Erro ao converter data:", e);
            return String(tsRaw);
          }
        }

        function parseActive(val) {
          if (val === true || val === 1) return true;
          const s = String(val || "").toLowerCase().trim();
          return s === "true" || s === "1" || s === "yes" || s === "on";
        }

        let sidebarVisible = true;
        btnToggleSidebar.onclick = () => {
          sidebarVisible = !sidebarVisible;
          if (sidebarVisible) {
            sidebar.style.display = "block";
            btnToggleSidebar.textContent = "Ocultar lista";
          } else {
            sidebar.style.display = "none";
            btnToggleSidebar.textContent = "Mostrar lista";
          }
          setTimeout(() => { map.invalidateSize(); }, 200);
        };

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution: "&copy; OpenStreetMap contributors"
        }).addTo(map);

        const markers = {};
        let autoFit = true;
        let lastCoordsAll = [];

        // Quando o usuário mexer no mapa, para de auto-enquadrar
        map.on("movestart", () => { autoFit = false; });
        map.on("zoomstart", () => { autoFit = false; });

        function setMarkerPopup(marker, html) {
          try {
            if (marker.getPopup && marker.getPopup()) {
              marker.getPopup().setContent(html);
            } else {
              marker.bindPopup(html);
            }
          } catch (e) {
            marker.bindPopup(html);
          }
        }

        function updateSessions(sessions) {
          const seen = new Set();
          const coordsAll = [];
          listEl.innerHTML = "";

          (sessions || []).forEach((s) => {
            // id robusto
            const id = s.id || s.session_id || s.code || s.token;
            if (!id) return;

            const lat = s.lat;
            const lon = s.lon;
            if (typeof lat !== "number" || typeof lon !== "number") return;

            seen.add(id);
            coordsAll.push([lat, lon]);

            let marker = markers[id];

            const nome = s.nome || s.display_name || s.name || "contato";
            const phone = s.phone || "";
            const lastRaw = s.updated_at || s.ts || "";
            const lastLocal = formatTsToLocal(lastRaw);

            const active = parseActive(s.active);
            const trackUrl = s.tracking_url || ("/t/" + encodeURIComponent(id));

            const popupHtml =
              "<b>" + nome + "</b>" +
              (phone ? "<br/>📱 " + phone : "") +
              "<br/>⏱ " + (lastLocal || "-") +
              "<br/>" +
              (active
                ? "<span style='color:#0f0;'>Ativo</span>"
                : "<span style='color:#f80;'>Encerrado</span>") +
              "<br/><a href='" + trackUrl +
              "' target='_blank' rel='noopener'>Abrir mapa detalhado</a>";

            const baseStyle = active
              ? { radius: 8, color: "#0f0", weight: 2, fillColor: "#0f0", fillOpacity: 0.7 }
              : { radius: 8, color: "#f80", weight: 2, fillColor: "#666", fillOpacity: 0.6 };

            if (!marker) {
              marker = L.circleMarker([lat, lon], baseStyle).addTo(map);
              markers[id] = marker;
            } else {
              marker.setLatLng([lat, lon]);
              marker.setStyle(baseStyle);
            }

            setMarkerPopup(marker, popupHtml);

            const li = document.createElement("li");
            li.innerHTML =
              "<b>" + nome + "</b>" +
              (phone ? " — " + phone : "") +
              " <small>(" + (active ? "ativo" : "encerrado") + ")</small>" +
              " <a href='#' class='encerrar' data-id='" + id + "'>encerrar</a>";

            li.onclick = () => {
              map.setView([lat, lon], 16);
              try { marker.openPopup(); } catch (e) {}
            };

            const linkEncerrar = li.querySelector("a.encerrar");
            if (linkEncerrar) {
              linkEncerrar.onclick = async (ev) => {
                ev.preventDefault();
                ev.stopPropagation();
                if (!confirm("Encerrar rastreamento deste contato?")) return;
                try {
                  const resp = await fetch(
                    "/api/live-track/session/" + encodeURIComponent(id),
                    {
                      method: "DELETE",
                      credentials: "same-origin",
                      cache: "no-store",
                      headers: { "Accept": "application/json" }
                    }
                  );
                  if (resp.ok) {
                    statusEl.textContent = "Sessão encerrada. Atualizando...";
                  } else {
                    statusEl.textContent = "Falha ao encerrar sessão (HTTP " + resp.status + ").";
                  }
                } catch (e) {
                  console.error(e);
                  statusEl.textContent = "Erro de comunicação ao encerrar sessão.";
                }
              };
            }

            listEl.appendChild(li);
          });

          // remove markers que sumiram
          Object.keys(markers).forEach((id) => {
            if (!seen.has(id)) {
              map.removeLayer(markers[id]);
              delete markers[id];
            }
          });

          lastCoordsAll = coordsAll.slice();

          if (coordsAll.length > 0) {
            if (autoFit) {
              const bounds = L.latLngBounds(coordsAll);
              map.fitBounds(bounds, { padding: [30, 30] });
            }
            statusEl.textContent = "Sessões: " + coordsAll.length;
          } else {
            statusEl.textContent = "Nenhum rastreamento ativo no momento.";
          }
        }

        btnFit.onclick = () => {
          if (lastCoordsAll.length > 0) {
            const bounds = L.latLngBounds(lastCoordsAll);
            map.fitBounds(bounds, { padding: [30, 30] });
          } else {
            map.setView([-14.2350, -51.9253], 4);
          }
          autoFit = true;
        };

        async function poll() {
          try {
            const resp = await fetch("/api/live-track/list?_=" + Date.now(), {
              credentials: "same-origin",
              cache: "no-store",
              headers: { "Accept": "application/json" }
            });
            if (!resp.ok) {
              statusEl.textContent = "Erro ao buscar sessões (HTTP " + resp.status + ").";
            } else {
              const data = await resp.json();
              updateSessions((data && data.sessions) ? data.sessions : []);
            }
          } catch (e) {
            console.error(e);
            statusEl.textContent = "Erro de comunicação com o servidor.";
          } finally {
            setTimeout(poll, 3000);
          }
        }

        poll();
      </script>
    </body>
    </html>
    """
    return HTMLResponse(html)


# =========================================================
# HTML DO MAPA PÚBLICO (/t/{session_id})
# =========================================================

def render_tracking_public_html(session_id: str) -> str:
    """
    Página pública (mobile/desktop):
      - usa /api/live-track/points/{id} como fonte principal (persistência SQLite)
      - fallback opcional para /api/live-track/track/{id} se o endpoint existir
      - tenta metadados via /api/live-track/list, mas DESLIGA se vier 401 (central protegida)
    """
    sid = str(session_id).strip()

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>Mapa - Anjo da Guarda</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">

  <style>
    * {{
      box-sizing: border-box;
    }}
    html, body {{
      height: 100%;
      margin: 0;
      padding: 0;
    }}
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #000;
      color: #eee;
      display: flex;
      flex-direction: column;
    }}
    .header {{
      padding: 8px 12px;
      font-size: 13px;
      background: #111;
      border-bottom: 1px solid #333;
      flex: 0 0 auto;
    }}
    .header strong {{
      display: block;
      font-size: 15px;
      margin-bottom: 2px;
    }}
    #info-line {{
      margin-top: 2px;
      opacity: 0.95;
    }}

    #wrapper {{
      flex: 1 1 auto;
      display: flex;
      min-height: 0;
    }}
    #map {{
      flex: 2;
      min-height: 0;
    }}
    #history-panel {{
      flex: 1;
      max-width: 360px;
      border-left: 1px solid #333;
      background: #111;
      padding: 6px 10px;
      overflow-y: auto;
      font-size: 12px;
      min-height: 0;
    }}
    #history-title {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-weight: bold;
      margin-bottom: 4px;
      font-size: 13px;
    }}
    .btn {{
      display: inline-block;
      padding: 3px 7px;
      border-radius: 3px;
      border: 1px solid #444;
      background: #222;
      color: #fff;
      cursor: pointer;
      user-select: none;
      font-size: 12px;
    }}
    .btn:hover {{ background: #333; }}
    #history-list {{
      margin: 0;
      padding: 0;
    }}
    .hist-item {{
      border-bottom: 1px solid #222;
      padding: 4px 0;
    }}
    .hist-item:last-child {{
      border-bottom: none;
    }}
    .hist-time {{
      color: #ddd;
    }}
    .hist-coord {{
      color: #aaa;
      font-size: 11px;
    }}
    .hist-last {{
      color: #0f0;
      font-weight: bold;
    }}

    @media (max-width: 768px) {{
      #wrapper {{
        flex-direction: column;
      }}
      #map {{
        height: 62%;
      }}
      #history-panel {{
        max-width: 100%;
        height: 38%;
        border-left: none;
        border-top: 1px solid #333;
      }}
    }}
  </style>

  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  />
</head>
<body>
  <div class="header">
    <strong>Mapa - Anjo da Guarda</strong>
    <div>Atualização em tempo quase real</div>
    <div id="info-line">Carregando sessão...</div>
  </div>

  <div id="wrapper">
    <div id="map"></div>
    <div id="history-panel">
      <div id="history-title">
        <span>Histórico de pontos</span>
        <span class="btn" id="btn-toggle-history">Ocultar</span>
      </div>
      <div id="history-list"></div>
    </div>
  </div>

  <script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin="">
  </script>

  <script>
    const SESSION_ID = "{sid}";

    const map = L.map('map');
    setTimeout(() => map.invalidateSize(), 50);

    L.tileLayer(
      'https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
      {{
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
      }}
    ).addTo(map);

    // default BR
    map.setView([-14.2350, -51.9253], 4);

    let marker = null;
    let polyline = null;
    let didFitPolyline = false;
    let hasFirstFix = false;

    // Se o usuário mexer, não ficar puxando pan
    let userInteracted = false;
    map.on('movestart', () => {{ userInteracted = true; }});
    map.on('zoomstart', () => {{ userInteracted = true; }});

    const infoLine = document.getElementById('info-line');
    const historyList = document.getElementById('history-list');
    const historyPanel = document.getElementById('history-panel');
    const btnToggleHistory = document.getElementById('btn-toggle-history');

    let historyVisible = true;
    btnToggleHistory.onclick = () => {{
      historyVisible = !historyVisible;
      if (historyVisible) {{
        historyPanel.style.display = 'block';
        btnToggleHistory.textContent = 'Ocultar';
      }} else {{
        historyPanel.style.display = 'none';
        btnToggleHistory.textContent = 'Mostrar';
      }}
      setTimeout(() => map.invalidateSize(), 200);
    }};

    function normalizeIsoTs(tsRaw) {{
      let iso = String(tsRaw || '').trim();
      if (!iso) return '';

      if (iso.indexOf('T') === -1 && iso.indexOf(' ') !== -1) {{
        iso = iso.replace(' ', 'T');
      }}

      iso = iso.replace(/(\\.[0-9]{{3}})[0-9]+/, '$1');

      if (!/(Z|[+\\-][0-9]{{2}}:?[0-9]{{2}})$/i.test(iso)) {{
        iso = iso + 'Z';
      }}

      return iso;
    }}

    function formatTsToLocal(tsRaw) {{
      if (!tsRaw) return '';
      try {{
        const iso = normalizeIsoTs(tsRaw);
        if (!iso) return '';

        const d = new Date(iso);
        if (isNaN(d.getTime())) {{
          return String(tsRaw);
        }}

        return d.toLocaleString('pt-BR', {{
          timeZone: 'America/Sao_Paulo',
          dateStyle: 'short',
          timeStyle: 'medium'
        }});
      }} catch (e) {{
        console.error('Erro ao converter data:', e);
        return String(tsRaw);
      }}
    }}

    function parseActive(val) {{
      if (val === true || val === 1) return true;
      const s = String(val || '').toLowerCase().trim();
      return s === 'true' || s === '1' || s === 'yes' || s === 'on';
    }}

    function renderHistory(points) {{
      historyList.innerHTML = '';

      const max = 200;
      const slice = (points.length > max) ? points.slice(points.length - max) : points;

      slice.forEach((p, idx) => {{
        const div = document.createElement('div');
        div.className = 'hist-item' + (idx === slice.length - 1 ? ' hist-last' : '');

        const tsText = formatTsToLocal(p.ts);
        const lat = (typeof p.lat === 'number') ? p.lat.toFixed(5) : p.lat;
        const lon = (typeof p.lon === 'number') ? p.lon.toFixed(5) : p.lon;

        const timeEl = document.createElement('div');
        timeEl.className = 'hist-time';
        timeEl.textContent = tsText || '-';

        const coordEl = document.createElement('div');
        coordEl.className = 'hist-coord';
        coordEl.textContent = lat + ', ' + lon;

        div.appendChild(timeEl);
        div.appendChild(coordEl);
        historyList.appendChild(div);
      }});

      historyList.scrollTop = historyList.scrollHeight;
    }}

    function applyPolyline(points) {{
      // só desenha se >= 2 pontos válidos
      const latlngs = (points || [])
        .filter(p => typeof p.lat === 'number' && typeof p.lon === 'number')
        .map(p => [p.lat, p.lon]);

      if (latlngs.length < 2) {{
        if (polyline) {{
          map.removeLayer(polyline);
          polyline = null;
          didFitPolyline = false;
        }}
        return;
      }}

      if (!polyline) {{
        polyline = L.polyline(latlngs, {{ color: '#00aaff', weight: 4 }}).addTo(map);
      }} else {{
        polyline.setLatLngs(latlngs);
      }}

      if (polyline && !didFitPolyline) {{
        didFitPolyline = true;
        try {{
          map.fitBounds(polyline.getBounds(), {{ padding: [30, 30] }});
        }} catch (e) {{
          console.log('fitBounds falhou', e);
        }}
      }}
    }}

    function applyMarkerFromLast(last) {{
      if (!last) return;

      const lat = last.lat;
      const lon = last.lon;
      if (lat == null || lon == null) return;

      const pos = [lat, lon];

      if (!hasFirstFix) {{
        hasFirstFix = true;
        map.setView(pos, 18);
      }}

      if (!marker) {{
        marker = L.marker(pos).addTo(map);
      }} else {{
        marker.setLatLng(pos);
      }}

      // não "puxa" o usuário se ele estiver explorando o mapa
      if (!userInteracted) {{
        try {{
          if (!map._animatingZoom) {{
            map.panTo(pos);
          }}
        }} catch (e) {{
          map.panTo(pos);
        }}
      }}
    }}

    let metaDisabled = false;

    async function fetchMetaFromList() {{
      if (metaDisabled) return null;
      try {{
        const resp = await fetch('/api/live-track/list?_=' + Date.now(), {{
          cache: 'no-store',
          headers: {{ 'Accept': 'application/json' }}
        }});
        if (resp.status === 401) {{
          // Central protegida -> não insistir no público
          metaDisabled = true;
          return null;
        }}
        if (!resp.ok) return null;
        const data = await resp.json();
        const sessions = (data && Array.isArray(data.sessions)) ? data.sessions : [];
        const found = sessions.find(s => (s.id || s.session_id || s.code || s.token) == SESSION_ID);
        return found || null;
      }} catch (e) {{
        return null;
      }}
    }}

    async function fetchPointsFromDb() {{
      const resp = await fetch('/api/live-track/points/' + encodeURIComponent(SESSION_ID) + '?_=' + Date.now(), {{
        cache: 'no-store',
        headers: {{ 'Accept': 'application/json' }}
      }});
      if (!resp.ok) return [];
      const db = await resp.json();
      const pts = (db && Array.isArray(db.points)) ? db.points : [];
      return pts.map(p => {{
        return {{
          lat: (typeof p.lat === 'number') ? p.lat : (p.lat != null ? Number(p.lat) : null),
          lon: (typeof p.lon === 'number') ? p.lon : (p.lon != null ? Number(p.lon) : null),
          ts: p.ts || p.created_at_utc || p.created_at || ''
        }};
      }}).filter(p => typeof p.lat === 'number' && typeof p.lon === 'number');
    }}

    async function fetchTrackFallback() {{
      // fallback se existir endpoint antigo /track
      try {{
        const resp = await fetch('/api/live-track/track/' + encodeURIComponent(SESSION_ID) + '?_=' + Date.now(), {{
          cache: 'no-store',
          headers: {{ 'Accept': 'application/json' }}
        }});
        if (!resp.ok) return [];
        const data = await resp.json();
        if (!data || data.ok === false) return [];

        const track = Array.isArray(data.track)
          ? data.track
          : (Array.isArray(data.points) ? data.points : []);

        return track.map(p => {{
          return {{
            lat: (typeof p.lat === 'number') ? p.lat : (p.lat != null ? Number(p.lat) : null),
            lon: (typeof p.lon === 'number') ? p.lon : (p.lon != null ? Number(p.lon) : null),
            ts: p.ts || data.updated_at || ''
          }};
        }}).filter(p => typeof p.lat === 'number' && typeof p.lon === 'number');
      }} catch (e) {{
        return [];
      }}
    }}

    function setInfoFromPoints(points) {{
      if (!points || !points.length) {{
        infoLine.textContent = 'Sessão: ' + SESSION_ID;
        return;
      }}
      const last = points[points.length - 1];
      const lastTs = last.ts ? formatTsToLocal(last.ts) : '-';
      infoLine.textContent = 'Sessão: ' + SESSION_ID + ' — Última atualização: ' + (lastTs || '-');
    }}

    async function atualizarTudo() {{
      // 1) pontos do DB (fonte principal)
      let points = [];
      try {{
        points = await fetchPointsFromDb();
      }} catch (e) {{
        points = [];
      }}

      // 2) fallback do track em memória (se DB ainda vazio)
      if (!points.length) {{
        const fb = await fetchTrackFallback();
        if (fb.length) points = fb;
      }}

      // 3) metadados (opcional; se 401 desliga)
      const meta = await fetchMetaFromList();
      if (meta) {{
        const nome = meta.nome || meta.display_name || meta.name || meta.phone || SESSION_ID;
        const phone = meta.phone ? (' — ' + meta.phone) : '';
        const ts = meta.updated_at || meta.ts || '';
        const active = parseActive(meta.active);
        infoLine.textContent =
          'Sessão: ' + nome + phone +
          ' — Última atualização: ' + (formatTsToLocal(ts) || '-') +
          (active ? '' : ' — (encerrada)');
      }} else {{
        setInfoFromPoints(points);
      }}

      if (!points.length) {{
        return;
      }}

      renderHistory(points);
      applyPolyline(points);

      const last = points[points.length - 1];
      applyMarkerFromLast(last);
    }}

    // primeira carga
    atualizarTudo();

    // atualiza a cada 15 segundos
    setInterval(atualizarTudo, 15000);
  </script>
</body>
</html>
"""
