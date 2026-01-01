from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["worklog-ui"])


@router.get("/worklog")
def worklog_page(req: Request):
    html = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>3G Brasil • Anjo da Guarda • Worklog</title>

  <style>
    :root{
      --bg0:#05060a;
      --bg1:#070b12;
      --card:#0b1320cc;
      --text:#e7eefc;
      --muted:#a9b4c9;
      --input:#0c1726;
      --c1:#0de7ff;
      --c2:#7c3aed;
      --ok:#9fe7b3;
      --err:#ffb4b4;
    }
    *{ box-sizing:border-box; }
    html,body{ height:100%; margin:0; }
    body{
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
      background:
        radial-gradient(900px 420px at 30% 25%, rgba(13,231,255,.20), transparent 60%),
        radial-gradient(900px 420px at 70% 65%, rgba(124,58,237,.18), transparent 60%),
        linear-gradient(180deg, var(--bg0), var(--bg1));
      color: var(--text);
      display:flex;
      align-items:flex-start;   /* <- permite conteúdo crescer */
      justify-content:center;
      padding: 18px;
      overflow-y:auto;          /* <- scroll se precisar */
    }

    .wrap{ width: 100%; max-width: 980px; }
    .brand{
      text-align:center;
      font-weight: 900;
      letter-spacing: .2px;
      margin: 0 0 14px;
      font-size: 22px;
      text-shadow:
        0 0 12px rgba(13,231,255,.30),
        0 0 18px rgba(124,58,237,.20);
    }

    .card{
      background: var(--card);
      border-radius: 18px;
      padding: 18px;
      border: 1px solid rgba(13,231,255,.35);
      box-shadow:
        0 0 0 1px rgba(124,58,237,.18) inset,
        0 0 18px rgba(13,231,255,.20),
        0 0 28px rgba(124,58,237,.14);
      backdrop-filter: blur(10px);
    }

    .grid{ display:grid; grid-template-columns: 1fr; gap: 12px; }
    .title{ margin: 0 0 8px; font-size: 18px; font-weight: 900; }

    label{
      display:block;
      font-size: 12px;
      color: var(--muted);
      margin: 2px 0 6px;
    }

    input, textarea, select{
      width: 100%;
      background: var(--input);
      color: var(--text);
      border: 1px solid rgba(13,231,255,.22);
      border-radius: 12px;
      padding: 12px 12px;
      outline: none;
    }
    input:focus, textarea:focus, select:focus{
      border-color: rgba(13,231,255,.55);
      box-shadow: 0 0 0 3px rgba(13,231,255,.12);
    }

    .row{ display:flex; gap: 10px; flex-wrap: wrap; align-items:center; }

    .btn{
      border: 0;
      border-radius: 12px;
      padding: 10px 16px;
      font-weight: 900;
      cursor: pointer;
      color: #001018;
      background: linear-gradient(90deg, rgba(13,231,255,.95), rgba(124,58,237,.75));
      box-shadow: 0 0 16px rgba(13,231,255,.22);
    }

    .btn-ghost{
      border: 1px solid rgba(13,231,255,.30);
      background: transparent;
      color: var(--text);
      border-radius: 12px;
      padding: 10px 16px;
      cursor: pointer;
      font-weight: 900;
    }

    .link{
      font-size: 13px;
      color: var(--c1);
      text-decoration: none;
      font-weight: 800;
      background: transparent;
      border: 0;
      padding: 0;
      cursor: pointer;
    }
    .link:hover{ text-decoration: underline; }

    .hidden{ display:none !important; }

    .msg{
      font-size: 12px;
      margin-top: 10px;
      white-space: pre-wrap;
    }
    .msg.ok{ color: var(--ok); }
    .msg.err{ color: var(--err); }

    .pw-wrap{ position: relative; }
    .pw-wrap input{ padding-right: 52px; }
    .eye{
      position:absolute;
      right: 8px;
      top: 50%;
      transform: translateY(-50%);
      width: 40px;
      height: 38px;
      border-radius: 10px;
      border: 1px solid rgba(13,231,255,.30);
      background: transparent;
      color: var(--text);
      cursor: pointer;
    }

    /* APP */
    .topbar{
      display:flex;
      justify-content: space-between;
      align-items:center;
      gap: 10px;
      margin-bottom: 10px;
    }
    .mini{
      font-size: 12px;
      color: var(--muted);
    }

    .entries{ margin-top: 14px; display:grid; gap: 10px; }
    .entry{
      border-radius: 14px;
      padding: 12px;
      border: 1px solid rgba(13,231,255,.15);
      background: rgba(5,6,10,.25);
    }
    .entry-head{
      display:flex;
      align-items:center;
      gap: 10px;
      margin-bottom: 6px;
    }
    .badge{
      font-size: 11px;
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid rgba(13,231,255,.22);
      color: var(--text);
      background: rgba(13,231,255,.08);
      font-weight: 900;
      letter-spacing: .3px;
    }
    .ts{ font-size: 12px; color: var(--muted); }
    .entry h3{ margin: 6px 0 4px; font-size: 16px; }
    .entry p{ margin: 0; color: var(--text); opacity: .95; line-height: 1.35; }

    /* LOGOUT sempre acessível */
    .logout-fab{
      position: fixed;
      right: 18px;
      top: 18px;
      z-index: 9999;
      padding: 10px 14px;
      border-radius: 12px;
      font-weight: 900;
      cursor: pointer;
      border: 1px solid rgba(13,231,255,.30);
      color: var(--text);
      background: rgba(6,12,20,.72);
      backdrop-filter: blur(10px);
      box-shadow: 0 0 16px rgba(13,231,255,.18), 0 0 26px rgba(124,58,237,.12);
    }
    .logout-fab:hover{ border-color: rgba(13,231,255,.55); }
  </style>
</head>

<body>
  <button class="logout-fab hidden" id="btnLogoutFab">Sair</button>

  <div class="wrap">
    <div class="brand">3G Brasil • Anjo da Guarda • Worklog</div>

    <div class="card">
      <!-- LOGIN -->
      <div class="grid" id="loginBox">
        <div class="title">Login</div>

        <div>
          <label for="email">E-mail</label>
          <input id="email" type="email" placeholder="seu@email.com" autocomplete="username" />
        </div>

        <div>
          <label for="pass">Senha</label>
          <div class="pw-wrap">
            <input id="pass" type="password" placeholder="••••••••" autocomplete="current-password" />
            <button type="button" class="eye" id="btnEye" aria-label="Mostrar/ocultar senha" title="Mostrar/ocultar senha">👁</button>
          </div>
        </div>

        <div class="row">
          <button class="btn" id="btnLogin">Entrar</button>
        </div>

        <div class="row" style="margin-top:6px">
          <button type="button" class="link" id="linkForgot">Esqueceu a senha? clique aqui</button>
        </div>

        <div class="msg hidden" id="msgOk"></div>
        <div class="msg hidden" id="msgErr"></div>
      </div>

      <!-- APP -->
      <div class="grid hidden" id="appBox">
        <div class="topbar">
          <div>
            <div class="title" style="margin:0">Worklog do dia</div>
            <div class="mini" id="miniInfo"></div>
          </div>
          <button class="btn-ghost" id="btnLogout">Logout</button>
        </div>

        <div class="row">
          <div style="flex:1; min-width:160px">
            <label for="entryType">Tipo</label>
            <select id="entryType">
              <option value="TASK">TASK</option>
              <option value="NOTE">NOTE</option>
              <option value="EVIDENCE">EVIDENCE</option>
              <option value="EMAIL">EMAIL</option>
            </select>
          </div>

          <div style="flex:2; min-width:220px">
            <label for="title">Título</label>
            <input id="title" type="text" placeholder="Ex: Ajuste Worklog UI" />
          </div>
        </div>

        <div>
          <label for="content">Conteúdo</label>
          <textarea id="content" rows="3" placeholder="Digite aqui..."></textarea>
        </div>

        <div class="row">
          <button class="btn" id="btnAdd">Adicionar</button>
        </div>

        <div>
          <label for="daySummary">Resumo do dia (para Encerrar)</label>
          <input id="daySummary" type="text" placeholder="Ex: Encerrando atividades do dia" />
        </div>

        <div class="row">
          <button class="btn-ghost" id="btnStop">Encerrar dia</button>
        </div>

        <div class="msg hidden" id="msgOk2"></div>
        <div class="msg hidden" id="msgErr2"></div>

        <div class="entries" id="entries"></div>
      </div>
    </div>
  </div>

<script>
  const $ = (id)=>document.getElementById(id);

  function showOk(id, txt){
    const ok = $(id);
    ok.textContent = txt || "";
    ok.classList.remove("hidden","err");
    ok.classList.add("ok");
    const errId = (id === "msgOk") ? "msgErr" : "msgErr2";
    $(errId).classList.add("hidden");
  }
  function showErr(id, txt){
    const err = $(id);
    err.textContent = txt || "";
    err.classList.remove("hidden","ok");
    err.classList.add("err");
    const okId = (id === "msgErr") ? "msgOk" : "msgOk2";
    $(okId).classList.add("hidden");
  }
  function clearMsgs(){
    $("msgOk").classList.add("hidden");
    $("msgErr").classList.add("hidden");
    $("msgOk2").classList.add("hidden");
    $("msgErr2").classList.add("hidden");
  }

  async function api(path, method, body){
    const opt = { method: method || "GET", headers: {} };
    if(body !== undefined){
      opt.headers["Content-Type"] = "application/json";
      opt.body = JSON.stringify(body);
    }
    const r = await fetch(path, opt);
    const ct = (r.headers.get("content-type") || "");
    let data = null;
    if(ct.includes("application/json")) data = await r.json().catch(()=>null);
    else data = await r.text().catch(()=>null);

    if(!r.ok){
      const msg = (data && data.detail) ? JSON.stringify(data.detail) : (data ? JSON.stringify(data) : (r.status+""));
      throw new Error(msg);
    }
    return data;
  }

  function showLogin(){
    $("loginBox").classList.remove("hidden");
    $("appBox").classList.add("hidden");
    $("btnLogoutFab").classList.add("hidden");
  }
  function showApp(){
    $("loginBox").classList.add("hidden");
    $("appBox").classList.remove("hidden");
    $("btnLogoutFab").classList.remove("hidden");
  }

  function fmtTs(ts){
    if(!ts) return "";
    try{ return new Date(ts).toLocaleString("pt-BR"); }
    catch(e){ return String(ts); }
  }

  function escapeHtml(s){
    return String(s||"")
      .replaceAll("&","&amp;")
      .replaceAll("<","&lt;")
      .replaceAll(">","&gt;")
      .replaceAll('"',"&quot;")
      .replaceAll("'","&#039;");
  }

  function renderEntries(entries){
    const box = $("entries");
    box.innerHTML = "";
    (entries || []).forEach(e=>{
      const div = document.createElement("div");
      div.className = "entry";
      div.innerHTML = `
        <div class="entry-head">
          <span class="badge">${(e.entry_type||"").toUpperCase()}</span>
          <span class="ts">${fmtTs(e.ts)}</span>
        </div>
        ${e.title ? `<h3>${escapeHtml(e.title)}</h3>` : ``}
        <p>${escapeHtml(e.content||"")}</p>
      `;
      box.appendChild(div);
    });
  }

  async function loadOrStartToday(){
    const r = await api("/api/worklog/today","GET");
    if(r && r.ok && !r.session){
      await api("/api/worklog/start","POST",{source:"Web"});
      return await api("/api/worklog/today","GET");
    }
    return r;
  }

  async function enterApp(){
    const r = await loadOrStartToday();
    showApp();
    const s = r.session;
    $("miniInfo").textContent = s
      ? `Início: ${fmtTs(s.started_at)}${s.ended_at ? " • Encerrado: " + fmtTs(s.ended_at) : ""}`
      : "";
    renderEntries(r.entries || []);
  }

  async function doLogoutAndBack(){
    try{ await api("/api/auth/logout","POST",{}); }catch(e){}
    window.location.href = "/worklog";
  }

  // eye toggle
  $("btnEye").addEventListener("click", ()=>{
    const p = $("pass");
    p.type = (p.type === "password") ? "text" : "password";
  });

  $("pass").addEventListener("keydown", (ev)=>{
    if(ev.key === "Enter") $("btnLogin").click();
  });

  // LOGIN
  $("btnLogin").addEventListener("click", async ()=>{
    try{
      clearMsgs();
      const email = $("email").value.trim();
      const password = $("pass").value;
      if(!email || !password) return showErr("msgErr","Informe e-mail e senha.");

      await api("/api/auth/login","POST",{email, password, source:"Web"});
      await enterApp();
    }catch(e){
      showErr("msgErr","Falha no login: " + (e.message || e));
    }
  });

  // FORGOT
  $("linkForgot").addEventListener("click", async (ev)=>{
    ev.preventDefault();
    ev.stopPropagation();
    try{
      clearMsgs();
      const email = $("email").value.trim();
      if(!email) return showErr("msgErr","Digite seu e-mail no campo acima.");

      const r = await api("/api/auth/forgot","POST",{email});

      if(r && r.debug_reset_link){
        showOk("msgOk","Link enviado. (DEBUG local) Abrindo tela de reset…");
        window.open(r.debug_reset_link, "_blank");
      } else {
        showOk("msgOk","Se o e-mail existir, um link de redefinição foi enviado.");
      }
    }catch(e){
      showErr("msgErr","Falha ao solicitar reset: " + (e.message || e));
    }
  });

  // ADD ENTRY
  $("btnAdd").addEventListener("click", async ()=>{
    try{
      clearMsgs();
      const entry_type = ($("entryType").value || "TASK").toUpperCase();
      const title = $("title").value.trim();
      const content = $("content").value.trim();
      if(!content) return showErr("msgErr2","Conteúdo obrigatório.");

      await api("/api/worklog/entry","POST",{entry_type, title: title || null, content});
      $("content").value = "";

      const r = await api("/api/worklog/today","GET");
      renderEntries(r.entries || []);
      showOk("msgOk2","Adicionado.");
    }catch(e){
      showErr("msgErr2","Erro ao adicionar: " + (e.message || e));
    }
  });

  // STOP DAY
  $("btnStop").addEventListener("click", async ()=>{
    try{
      clearMsgs();
      const day_summary = $("daySummary").value.trim() || null;
      await api("/api/worklog/stop","POST",{source:"Web", day_summary});
      const r = await api("/api/worklog/today","GET");
      $("miniInfo").textContent = r.session
        ? `Início: ${fmtTs(r.session.started_at)}${r.session.ended_at ? " • Encerrado: " + fmtTs(r.session.ended_at) : ""}`
        : "";
      showOk("msgOk2","Dia encerrado.");
    }catch(e){
      showErr("msgErr2","Erro ao encerrar: " + (e.message || e));
    }
  });

  // LOGOUT (botões)
  $("btnLogout").addEventListener("click", doLogoutAndBack);
  $("btnLogoutFab").addEventListener("click", doLogoutAndBack);

  // WATCHDOG (idle) + derrubar no refresh/fechar aba
  const IDLE_MIN = 10; // <- ajuste aqui (minutos)
  let lastAct = Date.now();

  function bump(){ lastAct = Date.now(); }
  ["mousemove","keydown","click","scroll","touchstart"].forEach(evt=>{
    document.addEventListener(evt, bump, {passive:true});
  });

  setInterval(async ()=>{
    const isInApp = !$("appBox").classList.contains("hidden");
    if(!isInApp) return;
    if(Date.now() - lastAct > IDLE_MIN*60*1000){
      await doLogoutAndBack();
    }
  }, 5000);

  window.addEventListener("beforeunload", ()=>{
    const isInApp = !$("appBox").classList.contains("hidden");
    if(!isInApp) return;
    try{
      fetch("/api/auth/logout", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: "{}",
        keepalive: true
      });
    }catch(e){}
  });

  // init: se já estiver logado, entra direto
  (async ()=>{
    try{ await enterApp(); }
    catch(e){ showLogin(); }
  })();
</script>

</body>
</html>
"""
    return HTMLResponse(content=html, headers={"Content-Type": "text/html; charset=utf-8"})


@router.get("/worklog/reset")
def worklog_reset_page(req: Request):
    html = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Redefinir senha • Worklog</title>
  <style>
    :root{ --bg0:#05060a; --bg1:#070b12; --card:#0b1320cc; --text:#e7eefc; --muted:#a9b4c9; --input:#0c1726; --c1:#0de7ff; --c2:#7c3aed; --ok:#9fe7b3; --err:#ffb4b4; }
    *{ box-sizing:border-box; }
    html,body{ height:100%; margin:0; }
    body{
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
      background:
        radial-gradient(900px 420px at 30% 25%, rgba(13,231,255,.20), transparent 60%),
        radial-gradient(900px 420px at 70% 65%, rgba(124,58,237,.18), transparent 60%),
        linear-gradient(180deg, var(--bg0), var(--bg1));
      color: var(--text);
      display:flex; align-items:flex-start; justify-content:center;
      padding: 18px;
      overflow-y:auto;
    }
    .wrap{ width:100%; max-width: 720px; }
    .brand{
      text-align:center; font-weight:900; font-size:22px; margin:0 0 14px;
      text-shadow: 0 0 12px rgba(13,231,255,.30), 0 0 18px rgba(124,58,237,.20);
    }
    .card{
      background: var(--card);
      border-radius: 18px;
      padding: 18px;
      border: 1px solid rgba(13,231,255,.35);
      box-shadow: 0 0 0 1px rgba(124,58,237,.18) inset, 0 0 18px rgba(13,231,255,.20), 0 0 28px rgba(124,58,237,.14);
      backdrop-filter: blur(10px);
    }
    .title{ margin:0 0 8px; font-size:18px; font-weight:900; }
    .mini{ font-size: 12px; color: var(--muted); }
    label{ display:block; font-size:12px; color: var(--muted); margin: 10px 0 6px; }
    input{
      width: 100%;
      background: var(--input);
      color: var(--text);
      border: 1px solid rgba(13,231,255,.22);
      border-radius: 12px;
      padding: 12px 12px;
      outline: none;
    }
    input:focus{ border-color: rgba(13,231,255,.55); box-shadow: 0 0 0 3px rgba(13,231,255,.12); }
    .row{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-top: 12px; }
    .btn{
      border:0; border-radius: 12px; padding: 10px 16px;
      font-weight:900; cursor:pointer; color:#001018;
      background: linear-gradient(90deg, rgba(13,231,255,.95), rgba(124,58,237,.75));
      box-shadow: 0 0 16px rgba(13,231,255,.22);
    }
    .btn-ghost{
      border:1px solid rgba(13,231,255,.30);
      background:transparent;
      color:var(--text);
      border-radius:12px;
      padding:10px 16px;
      cursor:pointer;
      font-weight:900;
    }
    .msg{ margin-top: 12px; font-size: 12px; white-space: pre-wrap; }
    .msg.ok{ color: var(--ok); }
    .msg.err{ color: var(--err); }
    .pw-wrap{ position:relative; }
    .pw-wrap input{ padding-right: 52px; }
    .eye{
      position:absolute; right:8px; top:50%; transform:translateY(-50%);
      width:40px; height:38px; border-radius:10px;
      border:1px solid rgba(13,231,255,.30);
      background:transparent; color:var(--text); cursor:pointer;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="brand">Redefinir senha • Worklog</div>

    <div class="card">
      <div class="title">Crie uma nova senha</div>
      <div class="mini">A senha deve ter no mínimo 8 caracteres.</div>

      <label for="p1">Nova senha</label>
      <div class="pw-wrap">
        <input id="p1" type="password" placeholder="••••••••" />
        <button type="button" class="eye" id="e1">👁</button>
      </div>

      <label for="p2">Confirmar senha</label>
      <div class="pw-wrap">
        <input id="p2" type="password" placeholder="••••••••" />
        <button type="button" class="eye" id="e2">👁</button>
      </div>

      <div class="row">
        <button class="btn" id="btnReset">Salvar nova senha</button>
        <button class="btn-ghost" id="btnBack">Voltar</button>
      </div>

      <div class="msg" id="m"></div>
    </div>
  </div>

<script>
  const $ = (id)=>document.getElementById(id);

  function msg(txt, kind){
    const el = $("m");
    el.className = "msg " + (kind || "");
    el.textContent = txt || "";
  }

  async function api(path, method, body){
    const opt = { method: method || "GET", headers: {} };
    if(body !== undefined){
      opt.headers["Content-Type"] = "application/json";
      opt.body = JSON.stringify(body);
    }
    const r = await fetch(path, opt);
    const ct = (r.headers.get("content-type") || "");
    let data = null;
    if(ct.includes("application/json")) data = await r.json().catch(()=>null);
    else data = await r.text().catch(()=>null);

    if(!r.ok){
      const e = (data && data.detail) ? JSON.stringify(data.detail) : (data ? JSON.stringify(data) : (r.status+""));
      throw new Error(e);
    }
    return data;
  }

  function toggle(id){
    const el = $(id);
    el.type = (el.type === "password") ? "text" : "password";
  }

  $("e1").addEventListener("click", ()=>toggle("p1"));
  $("e2").addEventListener("click", ()=>toggle("p2"));

  $("btnBack").addEventListener("click", ()=>{ window.location.href = "/worklog"; });

  $("btnReset").addEventListener("click", async ()=>{
    try{
      msg("", "");
      const token = (new URLSearchParams(window.location.search).get("token") || "").trim();
      if(token.length < 20) return msg("Token inválido ou ausente (link incompleto).", "err");

      const p1 = $("p1").value || "";
      const p2 = $("p2").value || "";
      if(p1.length < 8) return msg("Senha muito curta (mín. 8).", "err");
      if(p1 !== p2) return msg("As senhas não conferem.", "err");

      await api("/api/auth/reset","POST",{ token: token, password: p1 });
      msg("Senha atualizada com sucesso. Voltando para o login...", "ok");
      setTimeout(()=>{ window.location.href="/worklog"; }, 900);
    }catch(e){
      msg("Falha ao redefinir: " + (e.message || e), "err");
    }
  });
</script>
</body>
</html>
"""
    return HTMLResponse(content=html, headers={"Content-Type": "text/html; charset=utf-8"})
