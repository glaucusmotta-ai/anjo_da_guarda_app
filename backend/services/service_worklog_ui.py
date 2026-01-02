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
      align-items:center;
      justify-content:center;
      padding: 18px;
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

      /* garante que o Logout nunca fique "fora da tela" */
      max-height: calc(100vh - 140px);
      overflow: auto;
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

      /* fixo dentro do card */
      position: sticky;
      top: 0;
      z-index: 5;
      padding: 6px 0 10px;
      background: linear-gradient(180deg, rgba(11,19,32,.92), rgba(11,19,32,.30));
      backdrop-filter: blur(6px);
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

    /* DEPT */
    .dept-grid{
      display:grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    @media (max-width: 680px){
      .dept-grid{ grid-template-columns: 1fr; }
    }
    .dept-note{
      font-size: 12px;
      color: var(--muted);
      margin-top: 2px;
    }
    .dept-chip{
      display:inline-block;
      font-size: 11px;
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid rgba(13,231,255,.22);
      background: rgba(13,231,255,.08);
      margin-left: 8px;
      color: var(--text);
      font-weight: 900;
    }
  </style>
</head>

<body>
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

      <!-- DEPARTAMENTOS (abre após login) -->
      <div class="grid hidden" id="deptBox">
        <div class="topbar">
          <div>
            <div class="title" style="margin:0">Selecione o Departamento</div>
            <div class="mini">Isso define o contexto do seu worklog hoje.</div>
          </div>
          <button class="btn-ghost" id="btnLogout2">Logout</button>
        </div>

        <div class="dept-note">Escolha um departamento para entrar no Worklog do dia:</div>

        <div id="deptMain" class="dept-grid">
          <button class="btn-ghost" id="btnDeptEng">Engenharia / Desenvolvimento</button>
          <button class="btn-ghost" data-dept="Marketing">Marketing</button>
          <button class="btn-ghost" data-dept="Financeiro">Financeiro</button>
          <button class="btn-ghost" data-dept="RH">RH</button>
          <button class="btn-ghost" data-dept="Jurídico">Jurídico</button>
          <button class="btn-ghost" data-dept="Comercial">Comercial</button>
          <button class="btn-ghost" data-dept="Operações">Operações</button>
          <button class="btn-ghost" data-dept="TI / Infra">TI / Infra</button>
          <button class="btn-ghost" data-dept="Produto">Produto</button>
          <button class="btn-ghost" data-dept="Suporte">Suporte</button>
        </div>

        <div style="margin-top:14px; padding-top:12px; border-top:1px solid rgba(13,231,255,.15);">
          <div class="row">
            <button class="btn" id="btnWorkspaceD" type="button">Abrir Workspace</button>
            <div class="mini" id="wsInfo">Carregando status do Workspace…</div>
          </div>
        </div>

        <div id="deptEng" class="hidden">
          <div class="dept-note"><b>Engenharia / Desenvolvimento</b> — escolha a área:</div>
          <div class="dept-grid">
            <button class="btn-ghost" data-dept="Engenharia • iOS">iOS</button>
            <button class="btn-ghost" data-dept="Engenharia • Android">Android</button>
            <button class="btn-ghost" data-dept="Engenharia • Backend">Backend</button>
            <button class="btn-ghost" data-dept="Engenharia • Web">Web</button>
            <button class="btn-ghost" data-dept="Engenharia • DevOps">DevOps</button>
            <button class="btn-ghost" data-dept="Engenharia • QA">QA</button>
          </div>
          <div class="row" style="margin-top:10px">
            <button class="btn-ghost" id="btnDeptBack">Voltar</button>
          </div>
        </div>

        <div class="msg hidden" id="msgOkD"></div>
        <div class="msg hidden" id="msgErrD"></div>
      </div>

      <!-- APP -->
      <div class="grid hidden" id="appBox">
        <div class="topbar">
          <div>
            <div class="title" style="margin:0">
              Worklog do dia
              <span class="dept-chip" id="deptChip" style="display:none"></span>
            </div>
            <div class="mini" id="miniInfo"></div>
          </div>
          <div class="row" style="justify-content:flex-end">
            <button class="btn-ghost" id="btnWorkspaceA" type="button">Abrir Workspace</button>
            <button class="btn-ghost" id="btnChangeDept">Trocar depto</button>
            <button class="btn-ghost" id="btnLogout">Logout</button>
          </div>
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

  // PASSO 1 (LOCAL): link do VS Code no Windows (fallback)
  // (Passo 2 depois: backend retorna workspace_url remoto e a UI usa automaticamente)

  const DEPT_KEY = "worklog_dept"; // sessionStorage (não fica “pra sempre”)
  function getDept(){ return (sessionStorage.getItem(DEPT_KEY) || "").trim(); }
  function setDept(v){ sessionStorage.setItem(DEPT_KEY, (v||"").trim()); }
  function clearDept(){ sessionStorage.removeItem(DEPT_KEY); }

  function isVisible(id){
    const el = $(id);
    return !!(el && !el.classList.contains("hidden"));
  }

  function showOk(id, txt){
    const ok = $(id);
    if(!ok) return;
    ok.textContent = txt || "";
    ok.classList.remove("hidden","err");
    ok.classList.add("ok");
    const errId = (id === "msgOk") ? "msgErr" : (id==="msgOkD" ? "msgErrD" : "msgErr2");
    const err = $(errId);
    if(err) err.classList.add("hidden");
  }
  function showErr(id, txt){
    const err = $(id);
    if(!err) return;
    err.textContent = txt || "";
    err.classList.remove("hidden","ok");
    err.classList.add("err");
    const okId = (id === "msgErr") ? "msgOk" : (id==="msgErrD" ? "msgOkD" : "msgOk2");
    const ok = $(okId);
    if(ok) ok.classList.add("hidden");
  }
  function clearMsgs(){
    ["msgOk","msgErr","msgOk2","msgErr2","msgOkD","msgErrD"].forEach(id=>{
      const el = $(id);
      if(el) el.classList.add("hidden");
    });
  }

  async function api(path, method, body){
    const opt = { method: method || "GET", headers: {}, credentials: "same-origin" };
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
    $("deptBox").classList.add("hidden");
    $("appBox").classList.add("hidden");
  }
  function showDept(){
    $("loginBox").classList.add("hidden");
    $("deptBox").classList.remove("hidden");
    $("appBox").classList.add("hidden");
    // sempre que entrar na tela de depto, atualiza status
    refreshWorkspaceStatus();
  }
  function showApp(){
    $("loginBox").classList.add("hidden");
    $("deptBox").classList.add("hidden");
    $("appBox").classList.remove("hidden");
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

  function applyDeptChip(){
    const d = getDept();
    const chip = $("deptChip");
    if(d){
      chip.style.display = "inline-block";
      chip.textContent = d;
    } else {
      chip.style.display = "none";
      chip.textContent = "";
    }
  }

  async function enterApp(){
    const r = await loadOrStartToday();
    showApp();
    applyDeptChip();

    const s = r.session;
    $("miniInfo").textContent = s
      ? `Início: ${fmtTs(s.started_at)}${s.ended_at ? " • Encerrado: " + fmtTs(s.ended_at) : ""}`
      : "";
    renderEntries(r.entries || []);
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
      clearDept();             // sempre escolher depto ao logar
      showDept();              // <- agora vai para departamentos (e puxa status do workspace)
    }catch(e){
      showErr("msgErr","Falha no login: " + (e.message || e));
    }
  });

  // FORGOT: chama API (NÃO abre Outlook)
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

  // DEPT UI
  $("btnDeptEng").addEventListener("click", ()=>{
    $("deptMain").classList.add("hidden");
    $("deptEng").classList.remove("hidden");
  });
  $("btnDeptBack").addEventListener("click", ()=>{
    $("deptEng").classList.add("hidden");
    $("deptMain").classList.remove("hidden");
  });

  // clique em qualquer botão com data-dept
  document.addEventListener("click", async (ev)=>{
    const el = ev.target;
    if(!el) return;
    const dept = el.getAttribute && el.getAttribute("data-dept");
    if(!dept) return;

    try{
      clearMsgs();
      setDept(dept);
      showOk("msgOkD", "Departamento selecionado: " + dept);
      await enterApp();
    }catch(e){
      showErr("msgErrD", "Falha ao entrar: " + (e.message || e));
      showDept();
    }
  });

  // ADD ENTRY
  $("btnAdd").addEventListener("click", async ()=>{
    try{
      clearMsgs();
      const entry_type = ($("entryType").value || "TASK").toUpperCase();
      let title = $("title").value.trim();
      const content = $("content").value.trim();
      if(!content) return showErr("msgErr2","Conteúdo obrigatório.");

      const dept = getDept();
      if(dept){
        const prefix = "[" + dept + "] ";
        if(title){
          if(!title.startsWith(prefix)) title = prefix + title;
        } else {
          title = "[" + dept + "]";
        }
      }

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

  async function doLogout(){
    try{ await api("/api/auth/logout","POST",{}); }catch(e){}
    clearDept();
    location.reload();
  }

  // WORKSPACE (Passo 3 + Passo 4)
  async function refreshWorkspaceStatus(){
    const info = $("wsInfo"); // só existe na tela deptBox
    if(info) info.textContent = "Carregando status do Workspace…";

    try{
      const r = await api("/api/workspace/status","GET");

      // PASSO 3: mostrar exatamente o texto do backend (r.message)
      if(info){
        if(r && typeof r.message === "string" && r.message.trim()){
          info.textContent = r.message.trim();
        } else if(r && r.workspace_url){
          info.textContent = "Workspace disponível. Clique em Abrir Workspace.";
        } else {
          info.textContent = "Workspace ainda não configurado.";
        }
      }

      // labels
      const bD = $("btnWorkspaceD");
      const bA = $("btnWorkspaceA");
      if(bD) bD.textContent = "Abrir Workspace";
      if(bA) bA.textContent = "Abrir Workspace";

      return r;
    }catch(e){
      // sem enganar o usuário com "pronto" se a API falhar
      if(info) info.textContent = "Não foi possível ler o status do Workspace (verifique login/servidor).";
      return null;
    }
  }

  async function openWorkspace(){
    const okId = isVisible("appBox") ? "msgOk2" : "msgOkD";
    const errId = isVisible("appBox") ? "msgErr2" : "msgErrD";

    clearMsgs();
    showOk(okId, "Abrindo workspace…");

    // PASSO 4: abre a janela ANTES do await (evita bloqueio de popup)
    const w = window.open("about:blank", "_blank");

    try{
      const r = await api("/api/workspace/start","POST",{});
      let url = (r && r.workspace_url) ? String(r.workspace_url) : "";

      if(!url){
        if(w) w.close();
        throw new Error("Workspace sem URL. Verifique WORKLOG_WORKSPACE_ENABLED=1 e WORKLOG_WORKSPACE_PROVIDER=local_vscode.");
      }

      if(url.startsWith("/")) url = window.location.origin + url;

      if(w) w.location.href = url;
      else window.location.href = url;

      // fecha a aba em branco depois de disparar o protocolo
      setTimeout(() => {
        try { if(w) w.close(); } catch(e) {}
      }, 800);

      refreshWorkspaceStatus();
    }catch(e){
      if(w) w.close();
      showErr(errId, "Falha ao abrir workspace: " + (e.message || e));
    }
  }

  const btnWD = $("btnWorkspaceD");
  if(btnWD) btnWD.addEventListener("click", openWorkspace);

  const btnWA = $("btnWorkspaceA");
  if(btnWA) btnWA.addEventListener("click", openWorkspace);

  // LOGOUT
  $("btnLogout").addEventListener("click", doLogout);
  $("btnLogout2").addEventListener("click", doLogout);

  // TROCAR DEPTO
  $("btnChangeDept").addEventListener("click", ()=>{
    clearMsgs();
    clearDept();
    $("deptEng").classList.add("hidden");
    $("deptMain").classList.remove("hidden");
    showDept(); // também atualiza status do workspace
  });

  // init: se já estiver logado:
  // - se depto não escolhido => mostra dept
  // - se depto escolhido => entra no app
  (async ()=>{
    try{
      await api("/api/worklog/today","GET"); // testa se cookie é válido
      if(!getDept()){
        showDept();
      } else {
        await enterApp();
      }
    }catch(e){
      showLogin();
    }
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
      display:flex; align-items:center; justify-content:center;
      padding: 18px;
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
    const opt = { method: method || "GET", headers: {}, credentials: "same-origin" };
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
