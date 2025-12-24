# backend/services/service_mapa.py

import os
import sqlite3
import logging
from typing import List

from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)


# ========== HTML DA CENTRAL (/central) ==========

def central_page() -> HTMLResponse:
    html = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
      <meta charset="utf-8">
      <title>Central de Rastreamento - Anjo da Guarda</title>
      <meta name="viewport" content="width=device-width, initial-scale=1"/>

      <link
        rel="stylesheet"
        href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
        integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
        crossorigin=""
      />

      <style>
        * { box-sizing: border-box; }
        body {
          margin: 0;
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
        }
        .btn:hover { background: #333; }
        #container { display: flex; height: calc(100vh - 72px); }
        #map { flex: 2; }
        #sidebar {
          flex: 1;
          max-width: 360px;
          background: #111;
          border-left: 1px solid #333;
          padding: 8px 12px;
          overflow-y: auto;
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
      </style>
    </head>
    <body>
      <div id="topbar">
        <div id="title">🚨 Central de Rastreamento - Anjo da Guarda</div>
        <div id="status">Carregando sessões...</div>
        <div id="actions">
          <span class="btn" id="btn-fit">Visão geral</span>
          <span class="btn" id="btn-toggle-sidebar">Ocultar lista</span>
        </div>
      </div>
      <div id="container">
        <div id="map"></div>
        <div id="sidebar">
          <h3>Sessões ativas</h3>
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
              return tsRaw;
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
            return tsRaw;
          }
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

        map.on("movestart", () => { autoFit = false; });

        function updateSessions(sessions) {
          const seen = new Set();
          const coordsAll = [];
          listEl.innerHTML = "";

          sessions.forEach((s) => {
            if (typeof s.lat !== "number" || typeof s.lon !== "number") return;

            const id = s.id;
            seen.add(id);
            coordsAll.push([s.lat, s.lon]);

            let marker = markers[id];
            const nome = s.nome || "contato";
            const phone = s.phone || "";
            const lastRaw = s.updated_at || "";
            const lastLocal = formatTsToLocal(lastRaw);
            const active = !!s.active;
            const trackUrl = s.tracking_url || ("/t/" + encodeURIComponent(id));

            const popupHtml =
              "<b>" + nome + "</b>" +
              (phone ? "<br/>📱 " + phone : "") +
              "<br/>⏱ " + lastLocal +
              "<br/>" +
              (active
                ? "<span style='color:#0f0;'>Ativo</span>"
                : "<span style='color:#f80;'>Encerrado</span>") +
              "<br/><a href='" + trackUrl +
              "' target='_blank' rel='noopener'>Abrir trilha detalhada</a>";

            const baseStyle = active
              ? { radius: 8, color: "#0f0", weight: 2, fillColor: "#0f0", fillOpacity: 0.7 }
              : { radius: 8, color: "#f80", weight: 2, fillColor: "#666", fillOpacity: 0.6 };

            if (!marker) {
              marker = L.circleMarker([s.lat, s.lon], baseStyle).addTo(map);
              markers[id] = marker;
            } else {
              marker.setLatLng([s.lat, s.lon]);
              marker.setStyle(baseStyle);
            }
            marker.bindPopup(popupHtml);

            const li = document.createElement("li");
            li.innerHTML =
              "<b>" + nome + "</b>" +
              (phone ? " — " + phone : "") +
              " <small>(" + (active ? "ativo" : "encerrado") + ")</small>" +
              " <a href='#' class='encerrar' data-id='" + id + "'>encerrar</a>";

            li.onclick = () => {
              map.setView([s.lat, s.lon], 16);
              marker.openPopup();
            };

            const linkEncerrar = li.querySelector("a.encerrar");
            linkEncerrar.onclick = async (ev) => {
              ev.preventDefault();
              ev.stopPropagation();
              if (!confirm("Encerrar rastreamento deste contato?")) return;
              try {
                const resp = await fetch(
                  "/api/live-track/session/" + encodeURIComponent(id),
                  { method: "DELETE" }
                );
                if (resp.ok) {
                  li.remove();
                  if (markers[id]) {
                    map.removeLayer(markers[id]);
                    delete markers[id];
                  }
                  statusEl.textContent = "Sessão encerrada. Atualizando...";
                }
              } catch (e) {
                console.error(e);
              }
            };

            listEl.appendChild(li);
          });

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
            statusEl.textContent = "Sessões em memória: " + coordsAll.length;
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
            const resp = await fetch("/api/live-track/list");
            if (!resp.ok) {
              statusEl.textContent = "Erro ao buscar sessões.";
            } else {
              const data = await resp.json();
              updateSessions(data.sessions || []);
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


# ========== HTML DO RASTREAMENTO PÚBLICO (/t/{session_id}) ==========

def render_tracking_public_html(session_id: str) -> str:
    """
    HTML da página pública de rastreamento para celular / desktop.

    - Mapa em tela cheia com Leaflet + OSM
    - Linha azul da trilha
    - Painel lateral (desktop) / abaixo (mobile) com histórico de pontos
      (hora local + coordenadas)
    """
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <title>Rastreamento - Anjo da Guarda</title>
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
      }}
      .header {{
        padding: 8px 12px;
        font-size: 13px;
        background: #111;
        border-bottom: 1px solid #333;
      }}
      .header strong {{
        display: block;
        font-size: 15px;
        margin-bottom: 2px;
      }}
      #info-line {{
        margin-top: 2px;
      }}

      /* layout geral: mapa + histórico */
      #wrapper {{
        display: flex;
        height: calc(100% - 52px);
      }}
      #map {{
        flex: 2;
      }}
      #history-panel {{
        flex: 1;
        max-width: 360px;
        border-left: 1px solid #333;
        background: #111;
        padding: 6px 10px;
        overflow-y: auto;
        font-size: 12px;
      }}
      #history-title {{
        font-weight: bold;
        margin-bottom: 4px;
        font-size: 13px;
      }}
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

      /* em telas bem pequenas, coloca o histórico embaixo do mapa */
      @media (max-width: 768px) {{
        #wrapper {{
          flex-direction: column;
        }}
        #map {{
          height: 60%;
        }}
        #history-panel {{
          max-width: 100%;
          height: 40%;
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
        <strong>Rastreamento - Anjo da Guarda</strong>
        <div>Rastreamento em tempo quase real</div>
        <div id="info-line">Carregando sessão...</div>
    </div>

    <div id="wrapper">
      <div id="map"></div>
      <div id="history-panel">
        <div id="history-title">Histórico de pontos</div>
        <div id="history-list"></div>
      </div>
    </div>

    <script
      src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
      integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
      crossorigin="">
    </script>

    <script>
      const SESSION_ID = "{session_id}";

      const map = L.map('map');

      // Tile simples da central (OpenStreetMap)
      L.tileLayer(
        'https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
        {{
          maxZoom: 19,
          attribution: '&copy; OpenStreetMap contributors'
        }}
      ).addTo(map);

      let marker = null;
      let polyline = null;

      const infoLine = document.getElementById('info-line');
      const historyList = document.getElementById('history-list');

      function normalizeIsoTs(tsRaw) {{
        let iso = String(tsRaw || '').trim();
        if (!iso) return '';

        if (iso.indexOf('T') === -1 && iso.indexOf(' ') !== -1) {{
          iso = iso.replace(' ', 'T');
        }}

        // corta microssegundos para milissegundos: .593255 -> .593
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
            return tsRaw;
          }}

          return d.toLocaleString('pt-BR', {{
            timeZone: 'America/Sao_Paulo',
            dateStyle: 'short',
            timeStyle: 'medium'
          }});
        }} catch (e) {{
          console.error('Erro ao converter data:', e);
          return tsRaw;
        }}
      }}

      function renderHistory(track) {{
        historyList.innerHTML = '';
        track.forEach((p, idx) => {{
          const div = document.createElement('div');
          div.className = 'hist-item' + (idx === track.length - 1 ? ' hist-last' : '');

          const tsText = formatTsToLocal(p.ts);
          const lat = typeof p.lat === 'number' ? p.lat.toFixed(5) : p.lat;
          const lon = typeof p.lon === 'number' ? p.lon.toFixed(5) : p.lon;

          const timeEl = document.createElement('div');
          timeEl.className = 'hist-time';
          timeEl.textContent = tsText;

          const coordEl = document.createElement('div');
          coordEl.className = 'hist-coord';
          coordEl.textContent = lat + ', ' + lon;

          div.appendChild(timeEl);
          div.appendChild(coordEl);
          historyList.appendChild(div);
        }});

        // rola pro último ponto
        historyList.scrollTop = historyList.scrollHeight;
      }}

      function atualizarMapa() {{
        fetch('/api/live-track/track/' + SESSION_ID)
          .then(r => r.json())
          .then(data => {{
            if (!data || data.ok === false) {{
              infoLine.textContent = 'Sessão não encontrada ou encerrada.';
              return;
            }}

            // backend pode devolver "track" ou "points"
            const track = Array.isArray(data.track)
              ? data.track
              : (Array.isArray(data.points) ? data.points : []);

            if (!track.length) {{
              infoLine.textContent = 'Sessão encontrada, aguardando primeiros pontos...';
              return;
            }}

            // atualiza painel de histórico
            renderHistory(track);

            const last = track[track.length - 1] || {{}};
            const lat = last.lat;
            const lon = last.lon;

            if (lat == null || lon == null) {{
              infoLine.textContent = 'Sessão encontrada, mas sem coordenadas válidas.';
              return;
            }}

            const ts = last.ts || data.updated_at || '';
            const nome =
              data.nome ||
              data.name ||
              data.phone ||
              SESSION_ID;

            infoLine.textContent =
              'Sessão: ' + nome + ' — Última atualização: ' + formatTsToLocal(ts);

            // monta array [lat, lon] para polilinha
            const latlngs = track
              .filter(p => typeof p.lat === 'number' && typeof p.lon === 'number')
              .map(p => [p.lat, p.lon]);

            if (!latlngs.length) {{
              return;
            }}

            const pos = latlngs[latlngs.length - 1];

            // cria / atualiza linha azul
            if (!polyline) {{
              polyline = L.polyline(latlngs, {{ color: '#00aaff', weight: 4 }}).addTo(map);
              map.fitBounds(polyline.getBounds(), {{ padding: [30, 30] }});
            }} else {{
              polyline.setLatLngs(latlngs);
            }}

            // cria / move marcador
            if (!marker) {{
              marker = L.marker(pos).addTo(map);
            }} else {{
              marker.setLatLng(pos);
            }}

            // sempre acompanha o último ponto
            map.panTo(pos);
          }})
          .catch(err => {{
            console.error('Erro ao buscar trilha da sessão', err);
          }});
      }}

      // primeira carga
      atualizarMapa();
      // atualiza a cada 15 segundos
      setInterval(atualizarMapa, 15000);
    </script>
</body>
</html>
"""


# ========== FUNÇÕES DE BANCO PARA A TRILHA ==========

# Base deste arquivo: backend/services
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Raiz do projeto: C:\\dev\\anjo_da_guarda_app
ROOT_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", ".."))

# Pasta única de dados: C:\\dev\\anjo_da_guarda_app\\data
DATA_DIR = os.path.join(ROOT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Banco único do sistema
DB_PATH = os.path.join(DATA_DIR, "anjo.db")


def salvar_ponto_trilha(session_id: str, lat: float, lon: float, ts: str) -> None:
    """
    Salva um ponto da trilha no banco.
    `ts` deve ser um carimbo de tempo em UTC (isoformat).
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            INSERT INTO live_track_points (
                session_id,
                created_at_utc,
                lat,
                lon,
                ts
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, str(ts), float(lat), float(lon), str(ts)),
        )
        conn.commit()
    except Exception as e:
        try:
            logger.error("[TRACK] erro ao salvar ponto da trilha no banco: %s", e)
        except Exception:
            print("[TRACK] erro ao salvar ponto da trilha no banco:", e)
    finally:
        conn.close()


def listar_pontos_trilha(session_id: str) -> List[dict]:
    """
    Lista os pontos da trilha para a sessão, ordenados por created_at_utc.
    Retorna uma lista de dicts com chaves: session_id, lat, lon, ts.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                session_id,
                created_at_utc,
                lat,
                lon
            FROM live_track_points
            WHERE session_id = ?
            ORDER BY created_at_utc ASC
            """,
            (session_id,),
        ).fetchall()

        pontos = []
        for r in rows:
            pontos.append(
                {
                    "session_id": r["session_id"],
                    "lat": r["lat"],
                    "lon": r["lon"],
                    # Mantemos a chave "ts" para o restante do código
                    "ts": r["created_at_utc"],
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
        conn.close()
