from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["worklog-ui"])

HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Worklog • 3G Brasil • Anjo da Guarda</title>
  <style>
    :root{
      --bg:#0b1220; --card:#0f1a2e; --muted:#9aa4b2; --text:#e8eef6;
      --line:#1d2a44; --ok:#2dd4bf; --warn:#fbbf24; --bad:#fb7185;
      --btn:#15284b; --btn2:#0b3a53;
    }
    body{margin:0;background:linear-gradient(180deg,#070b14,#0b1220);color:var(--text);
      font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;}
    .wrap{max-width:980px;margin:0 auto;padding:20px;}
    .top{display:flex;gap:12px;align-items:center;justify-content:space-between;margin-bottom:14px;}
    .brand{font-weight:800;letter-spacing:.2px}
    .pill{font-size:12px;color:var(--muted);border:1px solid var(--line);padding:6px 10px;border-radius:999px}
    .grid{display:grid;grid-template-columns:1fr;gap:12px}
    @media(min-width:900px){.grid{grid-template-columns:360px 1fr}}
    .card{background:rgba(15,26,46,.92);border:1px solid var(--line);border-radius:14px;padding:14px}
    h2{font-size:14px;margin:0 0 10px 0;color:#cfe2ff}
    label{display:block;font-size:12px;color:var(--muted);margin:10px 0 6px}
    input,select,textarea{
      width:100%;box-sizing:border-box;background:#0b1324;color:var(--text);
      border:1px solid var(--line);border-radius:10px;padding:10px;font-size:14px;outline:none;
    }
    textarea{min-height:90px;resize:vertical}
    .row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
    .btns{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
    button{
      background:var(--btn);border:1px solid var(--line);color:var(--text);
      padding:9px 12px;border-radius:10px;cursor:pointer;font-weight:600;
    }
    button.primary{background:var(--btn2)}
    button.danger{background:#3a1220}
    button:disabled{opacity:.45;cursor:not-allowed}
    .msg{margin-top:10px;font-size:13px;color:var(--muted)}
    .msg.ok{color:var(--ok)} .msg.bad{color:var(--bad)} .msg.warn{color:var(--warn)}
    .statusLine{display:flex;flex-wrap:wrap;gap:10px;font-size:13px;color:var(--muted)}
    .statusLine b{color:var(--text)}
    table{width:100%;border-collapse:collapse;margin-top:10px}
    th,td{border-bottom:1px solid var(--line);padding:10px 8px;font-size:13px;vertical-align:top}
    th{color:#cfe2ff;text-align:left;font-size:12px}
    .small{font-size:12px;color:var(--muted)}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div class="brand">3G Brasil • <span style="color:#2dd4bf">Anjo da Guarda</span> • Worklog</div>
      <div class="pill">URL: https://anjo-track.3g-brasil.com/worklog</div>
    </div>

    <div class="grid">
      <div class="card" id="cardLogin">
        <h2>Login</h2>
        <label>E-mail</label>
        <input id="email" placeholder="seu@email.com" autocomplete="username"/>
        <label>Senha</label>
        <input id="password" placeholder="••••••••" type="password" autocomplete="current-password"/>
        <label>Fonte</label>
        <input id="source" value="Web"/>
        <div class="btns">
          <button class="primary" id="btnLogin">Entrar</button>
          <button id="btnTryToday">Verificar sessão</button>
        </div>
        <div class="msg" id="loginMsg"></div>
        <div class="small" style="margin-top:10px">
          Observação: use logout em PC de terceiros.
        </div>
      </div>

      <div class="card" id="cardPanel" style="display:none">
        <h2>Painel</h2>
        <div class="statusLine" id="statusLine"></div>

        <div class="btns">
          <button class="primary" id="btnStart">Iniciar (Start)</button>
          <button id="btnRefresh">Atualizar</button>
          <button class="danger" id="btnLogout">Logout</button>
        </div>

        <hr style="border:0;border-top:1px solid var(--line);margin:14px 0"/>

        <h2>Adicionar atividade</h2>
        <div class="row">
          <div>
            <label>Tipo</label>
            <select id="entryType">
              <option value="TASK">TASK</option>
              <option value="NOTE">NOTE</option>
              <option value="EVIDENCE">EVIDENCE</option>
              <option value="EMAIL">EMAIL</option>
            </select>
          </div>
          <div>
            <label>Título</label>
            <input id="entryTitle" placeholder="Ex.: Deploy / Revisão / Ajuste..."/>
          </div>
        </div>

        <label>Conteúdo (sem colar código)</label>
        <textarea id="entryContent" placeholder="Descreva o que foi feito + referência (arquivo/commit/ticket)."></textarea>

        <div class="btns">
          <button class="primary" id="btnAddEntry">Salvar Entry</button>
        </div>
        <div class="msg" id="entryMsg"></div>

        <hr style="border:0;border-top:1px solid var(--line);margin:14px 0"/>

        <h2>Encerrar</h2>
        <label>Resumo do dia</label>
        <textarea id="daySummary" placeholder="Resumo curto do dia."></textarea>
        <div class="btns">
          <button class="danger" id="btnStop">Encerrar (Stop)</button>
        </div>
        <div class="msg" id="stopMsg"></div>

        <hr style="border:0;border-top:1px solid var(--line);margin:14px 0"/>

        <h2>Atividades de hoje</h2>
        <div class="small" id="entriesHint"></div>
        <table>
          <thead>
            <tr><th>Hora (UTC)</th><th>Tipo</th><th>Título</th><th>Conteúdo</th></tr>
          </thead>
          <tbody id="entriesBody"></tbody>
        </table>
      </div>
    </div>
  </div>

<script>
  async function api(path, opts={}) {
    const res = await fetch(path, Object.assign({ credentials: 'include' }, opts));
    let data = null;
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) data = await res.json();
    else data = await res.text();
    return {res, data};
  }

  function setMsg(id, text, cls='') {
    const el = document.getElementById(id);
    el.className = 'msg ' + (cls||'');
    el.textContent = text || '';
  }

  function showPanel(show) {
    document.getElementById('cardLogin').style.display = show ? 'none' : 'block';
    document.getElementById('cardPanel').style.display = show ? 'block' : 'none';
  }

  function renderToday(payload) {
    const s = payload.session;
    const entries = payload.entries || [];
    const status = document.getElementById('statusLine');

    if (!s) {
      status.innerHTML = '<b>Status:</b> sem sessão hoje';
      document.getElementById('entriesBody').innerHTML = '';
      document.getElementById('entriesHint').textContent = '';
      return;
    }

    status.innerHTML =
      `<b>Sessão:</b> #${s.id} &nbsp;` +
      `<b>Início:</b> ${s.started_at} &nbsp;` +
      `<b>Fim:</b> ${s.ended_at || '--'} &nbsp;` +
      `<b>Fonte:</b> ${s.start_source || '--'}`;

    document.getElementById('entriesHint').textContent = entries.length ? `${entries.length} entries` : 'Nenhuma entry ainda.';
    const tb = document.getElementById('entriesBody');
    tb.innerHTML = entries.map(e => {
      const t = (e.ts||'').split('T')[1] ? (e.ts.split('T')[1].split('.')[0]||'') : (e.ts||'');
      return `<tr>
        <td>${t}</td>
        <td>${e.entry_type||''}</td>
        <td>${(e.title||'')}</td>
        <td>${(e.content||'')}</td>
      </tr>`;
    }).join('');
  }

  async function refresh() {
    const {res, data} = await api('/api/worklog/today');
    if (res.status === 200) {
      showPanel(true);
      renderToday(data);
      setMsg('loginMsg','', '');
      return true;
    }
    if (res.status === 401) {
      showPanel(false);
      return false;
    }
    setMsg('loginMsg', 'Erro ao verificar sessão: ' + (typeof data==='string' ? data : JSON.stringify(data)), 'bad');
    return false;
  }

  document.getElementById('btnTryToday').onclick = refresh;

  document.getElementById('btnLogin').onclick = async () => {
    setMsg('loginMsg','Entrando...', 'warn');
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const source = document.getElementById('source').value.trim() || 'Web';

    const {res, data} = await api('/api/auth/login', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({email, password, source})
    });

    if (res.status === 200 && data && data.ok) {
      setMsg('loginMsg','Login OK.', 'ok');
      await refresh();
    } else {
      setMsg('loginMsg','Falha no login: ' + (data.detail || JSON.stringify(data)), 'bad');
    }
  };

  document.getElementById('btnLogout').onclick = async () => {
    await api('/api/auth/logout', {method:'POST'});
    showPanel(false);
    setMsg('loginMsg','Logout feito.', 'ok');
  };

  document.getElementById('btnStart').onclick = async () => {
    const {res, data} = await api('/api/worklog/start', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({source:'Web'})
    });
    if (res.status === 200 && data.ok) {
      setMsg('entryMsg','Sessão iniciada/confirmada.', 'ok');
      await refresh();
    } else {
      setMsg('entryMsg','Erro no start: ' + (data.detail || JSON.stringify(data)), 'bad');
    }
  };

  document.getElementById('btnRefresh').onclick = refresh;

  document.getElementById('btnAddEntry').onclick = async () => {
    setMsg('entryMsg','Salvando...', 'warn');
    const entry_type = document.getElementById('entryType').value;
    const title = document.getElementById('entryTitle').value.trim() || null;
    const content = document.getElementById('entryContent').value.trim();

    if (!content) {
      setMsg('entryMsg','Conteúdo é obrigatório.', 'bad');
      return;
    }

    const {res, data} = await api('/api/worklog/entry', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({entry_type, title, content})
    });

    if (res.status === 200 && data.ok) {
      setMsg('entryMsg','Entry salva.', 'ok');
      document.getElementById('entryContent').value = '';
      await refresh();
    } else {
      setMsg('entryMsg','Erro ao salvar entry: ' + (data.detail || JSON.stringify(data)), 'bad');
    }
  };

  document.getElementById('btnStop').onclick = async () => {
    setMsg('stopMsg','Encerrando...', 'warn');
    const day_summary = document.getElementById('daySummary').value.trim() || null;

    const {res, data} = await api('/api/worklog/stop', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({source:'Web', day_summary})
    });

    if (res.status === 200 && data.ok) {
      setMsg('stopMsg','Sessão encerrada.', 'ok');
      await refresh();
    } else {
      setMsg('stopMsg','Erro no stop: ' + (data.detail || JSON.stringify(data)), 'bad');
    }
  };

  refresh();
</script>
</body>
</html>
"""

@router.get("/worklog", response_class=HTMLResponse)
def worklog_page():
    return HTML
