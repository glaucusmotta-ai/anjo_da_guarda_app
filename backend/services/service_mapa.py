# backend/services/service_mapa.py

import os
import sqlite3
from typing import Any, Dict, List

from fastapi.responses import HTMLResponse


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
        * {
          box-sizing: border-box;
        }
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
        #title {
          font-weight: bold;
        }
        #status {
          font-size: 12px;
          opacity: 0.8;
        }
        #actions {
          margin-top: 4px;
          font-size: 12px;
        }
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
        .btn:hover {
          background: #333;
        }
        #container {
          display: flex;
          height: calc(100vh - 72px);
        }
        #map {
          flex: 2;
        }
        #sidebar {
          flex: 1;
          max-width: 360px;
          background: #111;
          border-left: 1px solid #333;
          padding: 8px 12px;
          overflow-y: auto;
        }
        #sidebar h3 {
          margin-top: 4px;
          margin-bottom: 8px;
          font-size: 14px;
        }
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
        #sessions-list li:hover {
          background: #222;
        }
        #sessions-list small {
          color: #aaa;
        }
        #sessions-list a.encerrar {
          color: #f66;
          font-size: 11px;
          margin-left: 6px;
          text-decoration: none;
        }
        #sessions-list a.encerrar:hover {
          text-decoration: underline;
        }
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
          setTimeout(() => {
            map.invalidateSize();
          }, 200);
        };

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution: "&copy; OpenStreetMap contributors"
        }).addTo(map);

        const markers = {};
        let autoFit = true;
        let lastCoordsAll = [];

        map.on("movestart", () => {
          autoFit = false;
        });

        function updateSessions(sessions) {
          const seen = new Set();
          const coordsAll = [];
          listEl.innerHTML = "";

          sessions.forEach((s) => {
            if (typeof s.lat !== "number" || typeof s.lon !== "number") {
              return;
            }
            const id = s.id;
            seen.add(id);
            coordsAll.push([s.lat, s.lon]);

            let marker = markers[id];
            const nome = s.nome || "contato";
            const phone = s.phone || "";
            const last = s.updated_at || "";
            const active = !!s.active;
            const trackUrl = s.tracking_url || ("/t/" + encodeURIComponent(id));

            const popupHtml =
              "<b>" + nome + "</b>" +
              (phone ? "<br/>📱 " + phone : "") +
              "<br/>⏱ " + last +
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
    HTML da página pública de rastreamento para celular.
    Mesmo visual do mapa central (Leaflet + OpenStreetMap simples),
    atualiza a posição a cada 15 segundos.
    """
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <title>Rastreamento - Anjo da Guarda</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <!-- tudo em tela cheia no celular -->
    <style>
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
      #map {{
        width: 100%;
        height: calc(100% - 52px);
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

    <div id="map"></div>

    <script
      src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
      integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
      crossorigin="">
    </script>

    <script>
      const SESSION_ID = "{session_id}";

      const map = L.map('map');

      // Mesmo tile simples da central (OpenStreetMap, sem nome de loja)
      const tileLayer = L.tileLayer(
        'https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
        {{
          maxZoom: 19,
          attribution: '&copy; OpenStreetMap contributors'
        }}
      ).addTo(map);

      let marker = null;
      let hasFirstFix = false;

      function atualizarMapa() {{
        fetch('/api/live-track/list')
          .then(r => r.json())
          .then(data => {{
            // a API pode devolver {{sessions: [...]}} ou direto um array
            const lista = Array.isArray(data) ? data : (data.sessions || []);

            if (!Array.isArray(lista)) {{
              console.log('Resposta inesperada de /api/live-track/list', data);
              return;
            }}

            const sess = lista.find(s => {{
              const sid = s.id || s.session_id || s.code || s.token;
              return sid === SESSION_ID;
            }});

            if (!sess) {{
              document.getElementById('info-line').textContent =
                'Sessão não encontrada ou encerrada.';
              return;
            }}

            const lat =
              sess.lat ??
              sess.latitude ??
              sess.last_lat ??
              (sess.last_point && (sess.last_point.lat ?? sess.last_point.latitude));

            const lon =
              sess.lon ??
              sess.lng ??
              sess.longitude ??
              sess.last_lon ??
              (sess.last_point && (sess.last_point.lon ?? sess.last_point.lng ?? sess.last_point.longitude));

            if (lat == null || lon == null) {{
              document.getElementById('info-line').textContent =
                'Sessão encontrada, mas ainda sem posição.';
              return;
            }}

            const ts =
              sess.ts ||
              sess.last_ts ||
              (sess.last_point && (sess.last_point.ts || sess.last_point.time || sess.last_point.created_at)) ||
              '';

            const nome =
              sess.display_name ||
              sess.name ||
              sess.nome ||
              sess.phone ||
              SESSION_ID;

            document.getElementById('info-line').textContent =
              `Sessão: ${{nome}} — Última atualização: ${{ts}}`;

            const pos = [lat, lon];

            if (!hasFirstFix) {{
              hasFirstFix = true;
              map.setView(pos, 18);
              marker = L.marker(pos).addTo(map);
            }} else if (marker) {{
              marker.setLatLng(pos);
            }}
          }})
          .catch(err => {{
            console.error('Erro ao buscar lista de sessões', err);
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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "anjo_da_guarda.db")


def salvar_ponto_trilha(session_id: str, lat: float, lon: float, ts: str) -> None:
    """
    Salva um ponto da trilha na tabela live_track_points.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO live_track_points (session_id, lat, lon, ts)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, lat, lon, ts),
        )
        conn.commit()
    finally:
        conn.close()


def listar_pontos_trilha(session_id: str) -> List[Dict[str, Any]]:
    """
    Lista pontos da trilha ordenados por ts (ASC).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT lat, lon, ts
            FROM live_track_points
            WHERE session_id = ?
            ORDER BY ts ASC
            """,
            (session_id,),
        )
        rows = cur.fetchall()
        return [
            {"lat": row["lat"], "lon": row["lon"], "ts": row["ts"]}
            for row in rows
        ]
    finally:
        conn.close()
