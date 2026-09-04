(() => {
  const state = {
    preauthToken: null,
    accessToken: null,
    refreshToken: null,
    me: null,
    empresas: [],
    contatos: [],
    origensContato: [],
    tiposInteracao: [],
    empresaAtual: null,
    empresaUnidades: [],
    empresaAreas: [],
    empresaTiposUnidade: [],
    categorias: [],
    perguntas: [],
    perguntaDetalhe: null,
    formularios: [],
    builderFormulario: null,
    builderPerguntas: [],
    builderRegras: [],
    builderCatalogo: [],
    builderSelecionada: null,
    builderDetalhes: {},
    previewRespostas: {},
    builderModalSourceId: null,
    builderModalOptionId: null,
    builderModalCatalogo: [],
    builderModalSelected: new Set(),
    cloneOrigem: null,
    perguntaReturnToBuilderModal: false,
    builderFrozen: false,
  };

  const $ = (id) => document.getElementById(id);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const steps = ["loginStep", "mfaStep", "mfaSetupStep", "dashboardStep"];

  function showStep(id) {
    steps.forEach((step) => $(step).classList.toggle("hidden", step !== id));
    document.body.classList.toggle("admin-authenticated", id === "dashboardStep");
    hideMessage();
  }

  function showMessage(text, type = "error") {
    const el = $("message");
    el.textContent = text;
    el.className = `message ${type}`;
    if (document.body.classList.contains("admin-authenticated")) {
      window.clearTimeout(showMessage.timer);
      showMessage.timer = window.setTimeout(hideMessage, 3500);
    }
  }

  function hideMessage() {
    const el = $("message");
    el.textContent = "";
    el.className = "message hidden";
  }

  async function request(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    if (state.accessToken) headers.Authorization = `Bearer ${state.accessToken}`;

    const response = await fetch(path, { ...options, headers });
    let body = null;
    if (response.status !== 204) {
      try { body = await response.json(); } catch (_) {}
    }

    if (!response.ok) {
      if (response.status === 401 && state.accessToken) {
        state.accessToken = null;
        state.refreshToken = null;
        document.body.classList.remove("admin-authenticated");
        showStep("loginStep");
      }
      let detail = body?.detail || `Falha HTTP ${response.status}`;
      if (Array.isArray(detail)) detail = detail.map(x => x.msg || JSON.stringify(x)).join(" | ");
      const error = new Error(detail);
      error.status = response.status;
      throw error;
    }
    return body;
  }

  const esc = (v) => (v ?? "").toString().replace(/[&<>"']/g, (m) => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[m]));

  function qs(params) {
    const u = new URLSearchParams();
    Object.entries(params).forEach(([k,v]) => {
      if (v !== "" && v !== null && v !== undefined) u.set(k, v);
    });
    const s = u.toString();
    return s ? `?${s}` : "";
  }

  function showAdminView(name) {
    state.adminView = name;
    const map = {
      home:"adminHome",
      empresas:"adminEmpresas",
      unidades:"adminUnidades",
      areas:"adminAreas",
      contatos:"adminContatos",
      origensContato:"adminOrigensContato",
      tiposInteracao:"adminTiposInteracao",
      categorias:"adminCategorias",
      perguntas:"adminPerguntas",
      formularios:"adminFormularios",
      builder:"adminBuilder",
      builderPreview:"adminBuilderPreview"
    };
    Object.values(map).forEach(id => $(id).classList.add("hidden"));
    $(map[name] || map.home).classList.remove("hidden");
    if (name === "empresas") loadEmpresas();
    if (name === "unidades") loadOrgAdmin("unidades");
    if (name === "areas") loadOrgAdmin("areas");
    if (name === "contatos") loadContatos();
    if (name === "origensContato") loadCatalogoManutencao("origens");
    if (name === "tiposInteracao") loadCatalogoManutencao("tipos");
    if (name === "categorias") loadCategorias();
    if (name === "perguntas") loadPerguntas();
    if (name === "formularios") loadFormularios();
  }

  async function loadMe() {
    const me = await request("/api/auth/me");
    state.me = me;
    $("welcomeName").textContent = `Olá, ${me.nome}`;
    $("companyId").textContent = me.empresa_id || "Acesso global";
    $("profileName").textContent = me.perfil || "Global";
    $("superadminFlag").textContent = me.is_superadmin ? "Sim" : "Não";
    $("userEmail").textContent = me.email;
    showStep("dashboardStep");
    showAdminView("home");
  }

  async function finishAuthentication(body) {
    state.accessToken = body.access_token;
    state.refreshToken = body.refresh_token;
    state.preauthToken = null;
    await loadMe();
  }

  $("loginForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    hideMessage();
    const button = $("loginButton");
    button.disabled = true;
    button.textContent = "Entrando...";
    try {
      const body = await request("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: $("email").value.trim(), senha: $("senha").value, empresa_id: null }),
      });
      if (body.status === "AUTHENTICATED") return await finishAuthentication(body);
      state.preauthToken = body.preauth_token;
      if (body.status === "MFA_VERIFY") {
        $("mfaCode").value = ""; showStep("mfaStep"); $("mfaCode").focus(); return;
      }
      if (body.status === "MFA_SETUP") {
        const setup = await request(`/api/auth/mfa/setup?preauth_token=${encodeURIComponent(state.preauthToken)}`, { method:"POST" });
        $("mfaSecret").textContent = setup.secret;
        $("mfaSetupCode").value = "";
        showStep("mfaSetupStep"); $("mfaSetupCode").focus(); return;
      }
      throw new Error(`Status de autenticação não reconhecido: ${body.status}`);
    } catch (error) { showMessage(error.message || "Não foi possível entrar."); }
    finally { button.disabled = false; button.textContent = "Entrar"; }
  });

  $("mfaForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = $("mfaButton"); button.disabled = true; button.textContent = "Verificando...";
    try {
      const code = $("mfaCode").value.replace(/\D/g, "");
      if (code.length !== 6) throw new Error("Informe os 6 dígitos do autenticador.");
      await finishAuthentication(await request("/api/auth/mfa/verify", {
        method:"POST", body:JSON.stringify({preauth_token:state.preauthToken,codigo:code})
      }));
    } catch (error) { showMessage(error.message || "Código de verificação inválido."); }
    finally { button.disabled=false; button.textContent="Verificar e entrar"; }
  });

  $("mfaSetupForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = $("mfaSetupButton"); button.disabled=true; button.textContent="Confirmando...";
    try {
      const code = $("mfaSetupCode").value.replace(/\D/g, "");
      if (code.length !== 6) throw new Error("Informe os 6 dígitos do autenticador.");
      await finishAuthentication(await request("/api/auth/mfa/verify", {
        method:"POST", body:JSON.stringify({preauth_token:state.preauthToken,codigo:code})
      }));
    } catch (error) { showMessage(error.message || "Não foi possível confirmar o MFA."); }
    finally { button.disabled=false; button.textContent="Confirmar MFA e entrar"; }
  });

  $("logoutButton").addEventListener("click", async () => {
    try {
      if (state.accessToken) await request("/api/auth/logout", {
        method:"POST", body:JSON.stringify({refresh_token:state.refreshToken})
      });
    } catch (_) {}
    finally {
      state.preauthToken=null; state.accessToken=null; state.refreshToken=null; state.me=null;
      $("senha").value=""; $("mfaCode").value=""; $("mfaSetupCode").value="";
      showStep("loginStep"); $("email").focus();
    }
  });

  $("togglePassword").addEventListener("click", () => {
    const field=$("senha"), visible=field.type==="text";
    field.type=visible?"password":"text";
    $("togglePassword").textContent=visible?"Mostrar":"Ocultar";
  });
  $("mfaCode").addEventListener("input", e => e.target.value=e.target.value.replace(/\D/g,"").slice(0,6));
  $("mfaSetupCode").addEventListener("input", e => e.target.value=e.target.value.replace(/\D/g,"").slice(0,6));
  $("copySecret").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText($("mfaSecret").textContent); showMessage("Chave copiada.","info"); }
    catch (_) { showMessage("Selecione e copie a chave manualmente.","info"); }
  });
  $("backToLogin").addEventListener("click",()=>{state.preauthToken=null;showStep("loginStep")});
  $("backFromSetup").addEventListener("click",()=>{state.preauthToken=null;showStep("loginStep")});

  $$("[data-admin-view]").forEach(b => b.addEventListener("click", () => showAdminView(b.dataset.adminView)));
  $$("[data-close]").forEach(b => b.addEventListener("click", () => $(b.dataset.close).close()));

  function statusEmpresaLabel(v) {
    return ({EM_AVALIACAO:"Em avaliação",CLIENTE:"Cliente",DESCARTADA:"Descartada"})[v] || v || "—";
  }

  function statusContatoLabel(v) {
    return ({NOVO:"Novo",EM_ANALISE:"Em análise",QUALIFICADO:"Qualificado",DESCARTADO:"Descartado"})[String(v || "").toUpperCase()] || v || "—";
  }

  function fmtDate(v) {
    if (!v) return "—";
    try { return new Intl.DateTimeFormat("pt-BR", {dateStyle:"short", timeStyle:"short"}).format(new Date(v)); }
    catch (_) { return v; }
  }

  function empresaOptions({includeSemEmpresa=true, selected=""}={}) {
    const arr = state.empresas.filter(e => e.ativo && (includeSemEmpresa || e.slug !== "sem-empresa"));
    return arr.map(e => `<option value="${e.id}" ${String(e.id)===String(selected)?"selected":""}>${esc(e.nome)}${e.status?` — ${esc(statusEmpresaLabel(e.status))}`:""}</option>`).join("");
  }

  function refreshEmpresaSelects() {
    const filtro = $("filtroContatoEmpresa");
    if (filtro) {
      const atual = filtro.value;
      filtro.innerHTML = `<option value="">Todas as empresas</option>${empresaOptions({selected:atual})}`;
      filtro.value = atual;
    }
    const sel = $("contatoEmpresa");
    if (sel) {
      const atual = sel.value;
      sel.innerHTML = `<option value="">Sem empresa identificada</option>${empresaOptions({selected:atual})}`;
      sel.value = atual;
    }
  }

  function empresaManutencaoId() {
    return state.me?.empresa_id || state.empresas.find(e => e.slug === "mdp")?.id || state.empresas[0]?.id;
  }

  async function loadCatalogoManutencao(tipo) {
    try {
      await ensureEmpresas();
      const empresaId=empresaManutencaoId();
      if(!empresaId) throw new Error("Empresa ativa não definida.");
      const isOrigem=tipo==="origens";
      const path=isOrigem?`/api/admin/empresas/${empresaId}/origens-contato`:`/api/admin/empresas/${empresaId}/tipos-interacao`;
      const items=await request(path);
      if(isOrigem) state.origensContato=items; else state.tiposInteracao=items;
      const alvo=$(isOrigem?"listaOrigensContato":"listaTiposInteracao");
      alvo.innerHTML=items.length?`<div class="maintenance-table-wrap"><table class="maintenance-table"><thead><tr><th>Nome</th><th>Código</th><th>Descri├º├úo</th><th>Status</th><th>Ações</th></tr></thead><tbody>${items.map(x=>`<tr><td class="maintenance-name">${esc(x.nome)}</td><td><code>${esc(x.codigo)}</code></td><td>${esc(x.descricao||'—')}</td><td><span class="admin-tag ${x.ativo?'on':'off'}">${x.ativo?'Ativo':'Inativo'}</span></td><td><div class="admin-item-actions"><button type="button" data-edit-catalogo="${tipo}" data-id="${x.id}">Editar</button><button type="button" data-status-catalogo="${tipo}" data-id="${x.id}" data-ativo="${!x.ativo}">${x.ativo?'Inativar':'Ativar'}</button></div></td></tr>`).join('')}</tbody></table></div>`:`<div class="admin-empty">Nenhum registro.</div>`;
    } catch(e){showMessage(e.message);}
  }

  function openCatalogoManutencao(tipo,id=null){
    const items=tipo==="origens"?state.origensContato:state.tiposInteracao;
    const x=id?items.find(v=>v.id===id):null;
    $("catalogoTipo").value=tipo; $("catalogoId").value=x?.id||"";
    $("tituloCatalogoManutencao").textContent=(x?'Editar ':'Novo ')+(tipo==="origens"?'origem/canal':'tipo de interação');
    $("catalogoCodigo").value=x?.codigo||""; $("catalogoNome").value=x?.nome||"";
    $("catalogoOrdem").value=x?.ordem||""; $("catalogoDescricao").value=x?.descricao||"";
    $("dlgCatalogoManutencao").showModal();
  }

  async function carregarOrigensContato(empresaId, selecionada=null){
    if(!empresaId) return;
    const items=await request(`/api/admin/empresas/${empresaId}/origens-contato`);
    state.origensContato=items;
    $("contatoOrigem").innerHTML=items.filter(x=>x.ativo || x.id===selecionada).map(x=>`<option value="${x.id}">${esc(x.nome)}</option>`).join("");
    const escolha=selecionada || items.find(x=>x.codigo==="ADMIN" && x.ativo)?.id || items.find(x=>x.ativo)?.id;
    if(escolha) $("contatoOrigem").value=escolha;
  }

  async function ensureEmpresas() {
    if (!state.empresas.length) state.empresas = await request("/api/admin/empresas?ativo=true&incluir_sem_empresa=true");
    refreshEmpresaSelects();
  }

  async function loadEmpresas() {
    try {
      const busca = $("buscaEmpresa").value.trim();
      const status = $("filtroEmpresaStatus").value;
      const ativo = $("filtroEmpresaAtivo").value;
      state.empresas = await request(`/api/admin/empresas${qs({busca,status,ativo,incluir_sem_empresa:true})}`);
      renderEmpresas();
      refreshEmpresaSelects();
    } catch (e) { showMessage(e.message); }
  }

  function renderEmpresas() {
    $("listaEmpresas").innerHTML = state.empresas.length ? state.empresas.map(e => `
      <article class="admin-item entity-item">
        <div class="entity-icon">▣</div>
        <div>
          <h3>${esc(e.nome)}</h3>
          <p>${esc(e.cnpj || "CNPJ não informado")}${e.dominio ? ` • ${esc(e.dominio)}` : ""}</p>
          <div class="admin-tags">
            <span class="admin-tag ${e.status==="CLIENTE"?"on":e.status==="DESCARTADA"?"off":"eval"}">${esc(statusEmpresaLabel(e.status))}</span>
            <span class="admin-tag ${e.ativo?"on":"off"}">${e.ativo?"Ativa":"Inativa"}</span>
            ${e.slug==="sem-empresa"?`<span class="admin-tag">Técnica</span>`:""}
          </div>
        </div>
        <div class="admin-item-actions">
          <button type="button" data-open-empresa="${e.id}">Abrir</button>
          ${e.slug!=="sem-empresa" && e.ativo ? `<button type="button" class="danger" data-inativar-empresa="${e.id}">Inativar</button>` : ""}
        </div>
      </article>`).join("") : `<div class="admin-empty">Nenhuma empresa encontrada.</div>`;
    $$('[data-open-empresa]').forEach(b => b.onclick = () => openEmpresa(b.dataset.openEmpresa));
    $$('[data-inativar-empresa]').forEach(b => b.onclick = () => inativarEmpresa(b.dataset.inativarEmpresa));
  }

  function setCompanyTab(name) {
    $$('.company-tab').forEach(b => b.classList.toggle('active', b.dataset.companyTab === name));
    $$('.company-tab-panel').forEach(p => p.classList.toggle('hidden', p.dataset.companyPanel !== name));
  }

  function unidadeNome(id) {
    return state.empresaUnidades.find(u => String(u.id) === String(id))?.nome || 'Unidade não encontrada';
  }

  function tipoUnidadeNome(id) {
    return state.empresaTiposUnidade.find(t => String(t.id) === String(id))?.nome || 'Tipo não informado';
  }

  async function loadEmpresaDossier(id) {
    const [contatos, tipos, unidades, areas] = await Promise.all([
      request(`/api/admin/empresas/${id}/contatos`),
      request(`/api/admin/empresas/${id}/tipos-unidade`),
      request(`/api/admin/empresas/${id}/unidades`),
      request(`/api/admin/empresas/${id}/areas`),
    ]);
    state.empresaTiposUnidade = tipos;
    state.empresaUnidades = unidades;
    state.empresaAreas = areas;
    $('empresaResumoEstrutura').innerHTML = `
      <div class="company-summary-card"><strong>${unidades.length}</strong><span>Unidades</span></div>
      <div class="company-summary-card"><strong>${areas.length}</strong><span>Áreas</span></div>
      <div class="company-summary-card"><strong>${contatos.length}</strong><span>Contatos</span></div>`;
    $('empresaUnidadesResumo').innerHTML = unidades.length ? unidades.map(u => `
      <div class="org-row"><div class="org-row-main"><strong>${esc(u.nome)}</strong><span>${esc(u.codigo)} • ${esc(tipoUnidadeNome(u.tipo_unidade_id))}${u.cidade ? ` • ${esc(u.cidade)}${u.uf ? `/${esc(u.uf)}` : ''}` : ''} • ${u.ativo ? 'Ativa' : 'Inativa'}</span></div><div class="org-row-actions"><button type="button" data-edit-unidade="${u.id}">Editar</button><button type="button" data-status-unidade="${u.id}" data-ativo="${u.ativo}">${u.ativo ? 'Inativar' : 'Ativar'}</button></div></div>`).join('') : `<div class="admin-empty compact-empty">Empresa sem unidades cadastradas. Isso é permitido.</div>`;
    $('empresaAreasResumo').innerHTML = areas.length ? areas.map(a => `
      <div class="org-row"><div class="org-row-main"><strong>${esc(a.nome)}</strong><span>${esc(a.codigo)} • ${a.unidade_id ? `Unidade: ${esc(unidadeNome(a.unidade_id))}` : 'Corporativa'} • Ordem ${a.ordem} • ${a.ativo ? 'Ativa' : 'Inativa'}</span></div><div class="org-row-actions"><button type="button" data-edit-area="${a.id}">Editar</button><button type="button" data-status-area="${a.id}" data-ativo="${a.ativo}">${a.ativo ? 'Inativar' : 'Ativar'}</button></div></div>`).join('') : `<div class="admin-empty compact-empty">Empresa sem áreas cadastradas. Isso é permitido.</div>`;
    $('empresaContatosResumo').innerHTML = contatos.length ? contatos.map(c => `<button type="button" class="linked-contact" data-open-contact="${c.id}"><strong>${esc(c.nome)}</strong><span>${esc(c.origem_contato_nome || c.origem_primeiro_contato || c.origem || 'Origem não informada')} • ${esc(c.email || c.telefone || statusContatoLabel(c.status))}</span></button>`).join('') : `<div class="admin-empty compact-empty">Nenhum contato vinculado.</div>`;
    $$('[data-edit-unidade]', $('empresaUnidadesResumo')).forEach(b => b.onclick=()=>openUnidade(b.dataset.editUnidade));
    $$('[data-status-unidade]', $('empresaUnidadesResumo')).forEach(b => b.onclick=()=>toggleUnidade(b.dataset.statusUnidade, b.dataset.ativo !== 'true'));
    $$('[data-edit-area]', $('empresaAreasResumo')).forEach(b => b.onclick=()=>openArea(b.dataset.editArea));
    $$('[data-status-area]', $('empresaAreasResumo')).forEach(b => b.onclick=()=>toggleArea(b.dataset.statusArea, b.dataset.ativo !== 'true'));
    $$('[data-open-contact]', $('empresaContatosResumo')).forEach(b => b.onclick=()=>{ $('dlgEmpresa').close(); openContato(b.dataset.openContact); });
    if (state.adminView === 'unidades') renderOrgAdminList('unidades');
    if (state.adminView === 'areas') renderOrgAdminList('areas');
  }

  async function openEmpresa(id=null) {
    try {
      const e = id ? await request(`/api/admin/empresas/${id}`) : null;
      state.empresaAtual = e;
      $('empresaId').value = e?.id || '';
      $('tituloEmpresa').textContent = e ? e.nome : 'Nova empresa';
      $('empresaNome').value = e?.nome || '';
      $('empresaCnpj').value = e?.cnpj || '';
      $('empresaEmail').value = e?.email || '';
      $('empresaTelefone').value = e?.telefone || '';
      $('empresaDominio').value = e?.dominio || '';
      $('empresaStatus').value = e?.status || 'EM_AVALIACAO';
      $('empresaAtiva').checked = e?.ativo ?? true;
      $('empresaFichaBloco').classList.toggle('hidden', !e);
      if (e) { setCompanyTab('geral'); await loadEmpresaDossier(id); }
      $('dlgEmpresa').showModal();
    } catch(e) { showMessage(e.message); }
  }

  async function openUnidade(id=null) {
    try {
      if (!state.empresaAtual) return;
      const u=id ? await request(`/api/admin/unidades/${id}`) : null;
      $('unidadeId').value=u?.id||''; $('tituloUnidade').textContent=u?u.nome:'Nova unidade';
      $('unidadeTipo').innerHTML=state.empresaTiposUnidade.filter(t=>t.ativo || String(t.id)===String(u?.tipo_unidade_id)).map(t=>`<option value="${t.id}">${esc(t.nome)}${t.empresa_id?' (personalizado)':''}</option>`).join('');
      for (const [key,val] of Object.entries({Codigo:u?.codigo,Nome:u?.nome,Fantasia:u?.nome_fantasia,Cnpj:u?.cnpj,Email:u?.email,Telefone:u?.telefone,Cep:u?.cep,Logradouro:u?.logradouro,Numero:u?.numero,Complemento:u?.complemento,Bairro:u?.bairro,Cidade:u?.cidade,Uf:u?.uf})) $(`unidade${key}`).value=val||'';
      if(u?.tipo_unidade_id) $('unidadeTipo').value=u.tipo_unidade_id;
      $('unidadeAtiva').checked=u?.ativo??true; $('dlgUnidade').showModal();
    } catch(e){showMessage(e.message);}
  }

  async function toggleUnidade(id, ativo) {
    try { await request(`/api/admin/unidades/${id}/status`,{method:'PATCH',body:JSON.stringify({ativo})}); await loadEmpresaDossier(state.empresaAtual.id); showMessage(`Unidade ${ativo?'ativada':'inativada'}.`,'info'); } catch(e){showMessage(e.message);}
  }

  function refreshAreaScope() {
    const local=$('areaEscopo').value==='UNIDADE'; $('areaUnidadeLabel').classList.toggle('hidden',!local); $('areaUnidade').required=local;
  }

  async function openArea(id=null) {
    try {
      if (!state.empresaAtual) return;
      const a=id ? await request(`/api/admin/areas/${id}`) : null;
      $('areaId').value=a?.id||''; $('tituloArea').textContent=a?a.nome:'Nova área'; $('areaCodigo').value=a?.codigo||''; $('areaNome').value=a?.nome||''; $('areaDescricao').value=a?.descricao||''; $('areaAtiva').checked=a?.ativo??true;
      $('areaUnidade').innerHTML=state.empresaUnidades.filter(u=>u.ativo || String(u.id)===String(a?.unidade_id)).map(u=>`<option value="${u.id}">${esc(u.nome)}</option>`).join('');
      $('areaEscopo').value=a?.unidade_id?'UNIDADE':'CORPORATIVA'; if(a?.unidade_id)$('areaUnidade').value=a.unidade_id;
      const used=new Set(state.empresaAreas.filter(x=>String(x.unidade_id||'')===String(a?.unidade_id||'') && String(x.id)!==String(a?.id||'')).map(x=>Number(x.ordem))); let ordem=1; while(used.has(ordem))ordem++;
      $('areaOrdem').value=a?.ordem||ordem; refreshAreaScope();
      if (!a && !state.empresaUnidades.length) $('areaEscopo').value='CORPORATIVA'; refreshAreaScope(); $('dlgArea').showModal();
    } catch(e){showMessage(e.message);}
  }

  async function toggleArea(id, ativo) {
    try { await request(`/api/admin/areas/${id}/status`,{method:'PATCH',body:JSON.stringify({ativo})}); await loadEmpresaDossier(state.empresaAtual.id); showMessage(`Área ${ativo?'ativada':'inativada'}.`,'info'); } catch(e){showMessage(e.message);}
  }

  async function inativarEmpresa(id) {
    if (!confirm("Inativar esta empresa?")) return;
    try { await request(`/api/admin/empresas/${id}`, {method:"DELETE"}); showMessage("Empresa inativada.","info"); await loadEmpresas(); }
    catch(e){ showMessage(e.message); }
  }


  function orgEmpresaOptions(selected="") {
    return (state.empresas || [])
      .filter(e => e.slug !== 'sem-empresa')
      .map(e => `<option value="${e.id}" ${String(e.id)===String(selected)?'selected':''}>${esc(e.nome)}</option>`)
      .join('');
  }

  function renderOrgAdminList(kind) {
    const isUnidades = kind === 'unidades';
    const source = $(isUnidades ? 'empresaUnidadesResumo' : 'empresaAreasResumo');
    const target = $(isUnidades ? 'listaUnidades' : 'listaAreas');
    if (!source || !target) return;

    target.innerHTML = source.innerHTML;

    if (isUnidades) {
      $$('[data-edit-unidade]', target).forEach(b => b.onclick=()=>openUnidade(b.dataset.editUnidade));
      $$('[data-status-unidade]', target).forEach(b => b.onclick=()=>toggleUnidade(b.dataset.statusUnidade, b.dataset.ativo !== 'true'));
    } else {
      $$('[data-edit-area]', target).forEach(b => b.onclick=()=>openArea(b.dataset.editArea));
      $$('[data-status-area]', target).forEach(b => b.onclick=()=>toggleArea(b.dataset.statusArea, b.dataset.ativo !== 'true'));
    }
  }

  async function loadOrgAdmin(kind) {
    try {
      await ensureEmpresas();

      const isUnidades = kind === 'unidades';
      const select = $(isUnidades ? 'filtroUnidadeEmpresa' : 'filtroAreaEmpresa');
      const target = $(isUnidades ? 'listaUnidades' : 'listaAreas');
      const empresasValidas = (state.empresas || []).filter(e => e.slug !== 'sem-empresa');

      const anterior = select.value;
      select.innerHTML = `<option value="">Selecione a empresa</option>${orgEmpresaOptions(anterior)}`;

      let empresaId = anterior;
      if (!empresaId && state.empresaAtual?.id && empresasValidas.some(e => String(e.id)===String(state.empresaAtual.id))) {
        empresaId = state.empresaAtual.id;
      }
      if (!empresaId && empresasValidas.length === 1) empresaId = empresasValidas[0].id;

      if (!empresaId) {
        target.innerHTML = `<div class="admin-empty">Selecione uma empresa para visualizar ${isUnidades ? 'as unidades' : 'as Ã¡reas'}.</div>`;
        state.empresaAtual = null;
        return;
      }

      select.value = String(empresaId);
      state.empresaAtual = await request(`/api/admin/empresas/${empresaId}`);
      await loadEmpresaDossier(empresaId);
      renderOrgAdminList(kind);
    } catch (e) {
      showMessage(e.message);
    }
  }
  async function loadContatos() {
    try {
      await ensureEmpresas();
      const busca = $("buscaContato").value.trim();
      const status = $("filtroContatoStatus").value;
      const empresa_id = $("filtroContatoEmpresa").value;
      state.contatos = await request(`/api/admin/contatos${qs({busca,status,empresa_id})}`);
      renderContatos();
    } catch(e) { showMessage(e.message); }
  }

  function renderContatos() {
    $("listaContatos").innerHTML = state.contatos.length ? state.contatos.map(c => `
      <article class="admin-item entity-item">
        <div class="entity-icon">◎</div>
        <div>
          <h3>${esc(c.nome)}</h3>
          <p>${esc(c.empresa_nome || "Sem empresa")}${c.email?` • ${esc(c.email)}`:""}${c.telefone?` • ${esc(c.telefone)}`:""}</p>
          <div class="admin-tags">
            <span class="admin-tag">${esc(c.origem_contato_nome || c.origem_primeiro_contato || c.origem || "—")}</span>
            <span class="admin-tag ${String(c.status).toUpperCase()==="QUALIFICADO"?"on":String(c.status).toUpperCase()==="DESCARTADO"?"off":"eval"}">${esc(statusContatoLabel(c.status))}</span>
            <span class="admin-tag">${esc(c.tipo_solicitacao || "CONTATO")}</span>
          </div>
        </div>
        <div class="admin-item-actions"><button type="button" data-open-contato="${c.id}">Abrir</button></div>
      </article>`).join("") : `<div class="admin-empty">Nenhum contato encontrado.</div>`;
    $$('[data-open-contato]').forEach(b => b.onclick = () => openContato(b.dataset.openContato));
  }

  async function openContato(id=null) {
    try {
      await ensureEmpresas();
      const c = id ? await request(`/api/admin/contatos/${id}`) : null;
      $("contatoId").value = c?.id || "";
      $("tituloContato").textContent = c ? c.nome : "Novo contato";
      $("contatoNome").value = c?.nome || "";
      $("contatoEmail").value = c?.email || "";
      $("contatoTelefone").value = c?.telefone || "";
      $("contatoEmpresaInformada").value = c?.empresa_contato || "";
      $("contatoCnpj").value = c?.cnpj || "";
      $("contatoStatus").value = String(c?.status || "NOVO").toUpperCase();
      $("contatoTipo").value = c?.tipo_solicitacao || "CONTATO";
      await carregarOrigensContato(c?.empresa_id || empresaManutencaoId(), c?.origem_contato_id || null);
      $("contatoSegmento").value = c?.segmento || "";
      $("contatoCidade").value = c?.cidade || "";
      $("contatoUf").value = c?.uf || "";
      $("contatoSiteInstagram").value = c?.site_instagram || "";
      $("contatoMensagem").value = c?.mensagem || "";
      refreshEmpresaSelects();
      if (c?.empresa_id) $("contatoEmpresa").value = c.empresa_id;
      $("contatoAcoesEmpresa").classList.toggle("hidden", !c);
      $("criarEmpresaDoContato").disabled = !c || (!c.empresa_contato && !c.cnpj);
      $("dlgContato").showModal();
    } catch(e) { showMessage(e.message); }
  }

  function contatoPayload() {
    return {
      nome: $("contatoNome").value.trim(),
      email: $("contatoEmail").value.trim() || null,
      telefone: $("contatoTelefone").value.trim() || null,
      empresa_contato: $("contatoEmpresaInformada").value.trim() || null,
      cnpj: $("contatoCnpj").value.trim() || null,
      status: $("contatoStatus").value,
      tipo_solicitacao: $("contatoTipo").value,
      origem_contato_id: $("contatoOrigem").value || null,
      segmento: $("contatoSegmento").value.trim() || null,
      cidade: $("contatoCidade").value.trim() || null,
      uf: $("contatoUf").value.trim().toUpperCase() || null,
      site_instagram: $("contatoSiteInstagram").value.trim() || null,
      mensagem: $("contatoMensagem").value.trim() || null,
    };
  }

  $("novaOrigemContato").addEventListener("click",()=>openCatalogoManutencao("origens"));
  $("novoTipoInteracao").addEventListener("click",()=>openCatalogoManutencao("tipos"));
  $("contatoEmpresa").addEventListener("change",()=>carregarOrigensContato($("contatoEmpresa").value || empresaManutencaoId()));
  document.addEventListener("click",async ev=>{
    const edit=ev.target.closest("[data-edit-catalogo]"); if(edit){openCatalogoManutencao(edit.dataset.editCatalogo,edit.dataset.id);return;}
    const st=ev.target.closest("[data-status-catalogo]"); if(st){try{const base=st.dataset.statusCatalogo==="origens"?"origens-contato":"tipos-interacao";await request(`/api/admin/${base}/${st.dataset.id}/status`,{method:"PATCH",body:JSON.stringify({ativo:st.dataset.ativo==="true"})});await loadCatalogoManutencao(st.dataset.statusCatalogo);}catch(e){showMessage(e.message);} }
  });
  $("formCatalogoManutencao").addEventListener("submit",async ev=>{ev.preventDefault();try{const tipo=$("catalogoTipo").value,id=$("catalogoId").value,empresaId=empresaManutencaoId(),base=tipo==="origens"?"origens-contato":"tipos-interacao";const payload={codigo:$("catalogoCodigo").value.trim(),nome:$("catalogoNome").value.trim(),descricao:$("catalogoDescricao").value.trim()||null,ordem:$("catalogoOrdem").value?Number($("catalogoOrdem").value):null};await request(id?`/api/admin/${base}/${id}`:`/api/admin/empresas/${empresaId}/${base}`,{method:id?"PUT":"POST",body:JSON.stringify(payload)});$("dlgCatalogoManutencao").close();await loadCatalogoManutencao(tipo);showMessage("Registro salvo.","info");}catch(e){showMessage(e.message);}});

  $("novaEmpresa").addEventListener("click", () => openEmpresa());
  $("novoContato").addEventListener("click", () => openContato());
  $("buscaEmpresa").addEventListener("input", () => { clearTimeout(loadEmpresas.t); loadEmpresas.t=setTimeout(loadEmpresas,250); });
  $("filtroEmpresaStatus").addEventListener("change", loadEmpresas);
  $("filtroEmpresaAtivo").addEventListener("change", loadEmpresas);
  $("buscaContato").addEventListener("input", () => { clearTimeout(loadContatos.t); loadContatos.t=setTimeout(loadContatos,250); });
  $("filtroContatoStatus").addEventListener("change", loadContatos);
  $("filtroContatoEmpresa").addEventListener("change", loadContatos);

  $$('.company-tab').forEach(b => b.addEventListener('click',()=>setCompanyTab(b.dataset.companyTab)));
  $('filtroUnidadeEmpresa').addEventListener('change',()=>loadOrgAdmin('unidades'));
  $('filtroAreaEmpresa').addEventListener('change',()=>loadOrgAdmin('areas'));
  $('novaUnidadeAdmin').addEventListener('click',()=>{
    if (!state.empresaAtual?.id) return showMessage('Selecione uma empresa.');
    openUnidade();
  });
  $('novaAreaAdmin').addEventListener('click',()=>{
    if (!state.empresaAtual?.id) return showMessage('Selecione uma empresa.');
    openArea();
  });
  $('novaUnidade').addEventListener('click',()=>openUnidade());
  $('novaArea').addEventListener('click',()=>openArea());
  $('areaEscopo').addEventListener('change',refreshAreaScope);

  $('formUnidade').addEventListener('submit', async ev => {
    ev.preventDefault();
    try {
      const id=$('unidadeId').value, empresaId=state.empresaAtual.id;
      const payload={tipo_unidade_id:$('unidadeTipo').value,codigo:$('unidadeCodigo').value.trim(),nome:$('unidadeNome').value.trim(),nome_fantasia:$('unidadeFantasia').value.trim()||null,cnpj:$('unidadeCnpj').value.trim()||null,email:$('unidadeEmail').value.trim()||null,telefone:$('unidadeTelefone').value.trim()||null,cep:$('unidadeCep').value.trim()||null,logradouro:$('unidadeLogradouro').value.trim()||null,numero:$('unidadeNumero').value.trim()||null,complemento:$('unidadeComplemento').value.trim()||null,bairro:$('unidadeBairro').value.trim()||null,cidade:$('unidadeCidade').value.trim()||null,uf:$('unidadeUf').value.trim().toUpperCase()||null,ativo:$('unidadeAtiva').checked};
      await request(id?`/api/admin/unidades/${id}`:`/api/admin/empresas/${empresaId}/unidades`,{method:id?'PUT':'POST',body:JSON.stringify(payload)}); $('dlgUnidade').close(); await loadEmpresaDossier(empresaId); setCompanyTab('unidades'); showMessage(id?'Unidade atualizada.':'Unidade criada.','info');
    } catch(e){showMessage(e.message);}
  });

  $('formArea').addEventListener('submit', async ev => {
    ev.preventDefault();
    try {
      const id=$('areaId').value, empresaId=state.empresaAtual.id, local=$('areaEscopo').value==='UNIDADE';
      if(local && !$('areaUnidade').value) throw new Error('Selecione a unidade da área.');
      const payload={unidade_id:local?$('areaUnidade').value:null,codigo:$('areaCodigo').value.trim(),nome:$('areaNome').value.trim(),descricao:$('areaDescricao').value.trim()||null,ordem:Number($('areaOrdem').value),ativo:$('areaAtiva').checked};
      await request(id?`/api/admin/areas/${id}`:`/api/admin/empresas/${empresaId}/areas`,{method:id?'PUT':'POST',body:JSON.stringify(payload)}); $('dlgArea').close(); await loadEmpresaDossier(empresaId); setCompanyTab('areas'); showMessage(id?'Área atualizada.':'Área criada.','info');
    } catch(e){showMessage(e.message);}
  });

  $("formEmpresa").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const id=$("empresaId").value;
      const payload={
        nome:$("empresaNome").value.trim(), cnpj:$("empresaCnpj").value.trim()||null,
        email:$("empresaEmail").value.trim()||null, telefone:$("empresaTelefone").value.trim()||null,
        dominio:$("empresaDominio").value.trim()||null, status:$("empresaStatus").value,
        ativo:$("empresaAtiva").checked
      };
      await request(id?`/api/admin/empresas/${id}`:"/api/admin/empresas", {method:id?"PUT":"POST", body:JSON.stringify(payload)});
      $("dlgEmpresa").close(); state.empresas=[]; await loadEmpresas(); showMessage(id?"Empresa atualizada.":"Empresa criada.","info");
    } catch(e){ showMessage(e.message); }
  });

  $("formContato").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const id=$("contatoId").value;
      const empresaId=$("contatoEmpresa").value;
      const payload=contatoPayload();
      if (!id) payload.empresa_id = empresaId || null;
      const salvo=await request(id?`/api/admin/contatos/${id}`:"/api/admin/contatos", {method:id?"PUT":"POST", body:JSON.stringify(payload)});
      if (id && empresaId && String(empresaId)!==String(salvo.empresa_id)) {
        await request(`/api/admin/contatos/${id}/empresa`, {method:"PUT", body:JSON.stringify({empresa_id:empresaId})});
      }
      $("dlgContato").close(); state.contatos=[]; state.empresas=[]; await loadContatos(); showMessage(id?"Contato atualizado.":"Contato criado.","info");
    } catch(e){ showMessage(e.message); }
  });

  $("criarEmpresaDoContato").addEventListener("click", async () => {
    const id=$("contatoId").value;
    if (!id) return;
    const nome=$("contatoEmpresaInformada").value.trim();
    if (!nome) { showMessage("Informe o nome da empresa no contato antes de criar."); return; }
    if (!confirm(`Criar a empresa "${nome}" em avaliação e vincular este contato?`)) return;
    try {
      const c=await request(`/api/admin/contatos/${id}/criar-empresa`, {method:"POST", body:JSON.stringify({
        nome, cnpj:$("contatoCnpj").value.trim()||null,
        email:$("contatoEmail").value.trim()||null,
        telefone:$("contatoTelefone").value.trim()||null,
        status:"EM_AVALIACAO"
      })});
      state.empresas=[]; await ensureEmpresas(); $("contatoEmpresa").value=c.empresa_id; showMessage(`Empresa criada e contato vinculado a ${c.empresa_nome}.`,"info");
    } catch(e){ showMessage(e.message); }
  });

  async function loadCategorias() {
    try {
      const ativo = $("filtroCategoriaStatus").value;
      state.categorias = await request(`/api/diagnostico/categorias${qs({ativo})}`);
      renderCategorias();
      refreshCategoriaSelects();
    } catch (e) { showMessage(e.message); }
  }

  function renderCategorias() {
    const busca = $("buscaCategoria").value.trim().toLowerCase();
    const list = state.categorias.filter(c => !busca ||
      c.nome.toLowerCase().includes(busca) || (c.descricao || "").toLowerCase().includes(busca));
    $("listaCategorias").innerHTML = list.length ? list.map(c => `
      <article class="admin-item">
        <div class="admin-item-order">ORDEM<strong>${c.ordem}</strong></div>
        <div>
          <h3>${esc(c.nome)}</h3>
          <p>${esc(c.descricao || "Sem descrição")}</p>
          <div class="admin-tags">
            <span class="admin-tag">${c.empresa_id ? "Empresa" : "Global MDP"}</span>
            <span class="admin-tag ${c.ativo ? "on" : "off"}">${c.ativo ? "Ativa" : "Inativa"}</span>
          </div>
        </div>
        <div class="admin-item-actions">
          <button type="button" data-edit-cat="${c.id}">Editar</button>
          <button type="button" class="${c.ativo ? "danger" : ""}" data-toggle-cat="${c.id}">${c.ativo ? "Inativar" : "Ativar"}</button>
        </div>
      </article>`).join("") : `<div class="admin-empty">Nenhuma categoria encontrada.</div>`;

    $$("[data-edit-cat]").forEach(b => b.onclick = () => openCategoria(b.dataset.editCat));
    $$("[data-toggle-cat]").forEach(b => b.onclick = () => toggleCategoria(b.dataset.toggleCat));
  }

  function refreshCategoriaSelects() {
    const cats = state.categorias.filter(c => c.ativo).sort((a,b)=>a.ordem-b.ordem);
    const opts = cats.map(c => `<option value="${c.id}">${esc(c.nome)}</option>`).join("");
    const currentFilter = $("filtroCategoriaPergunta").value;
    $("filtroCategoriaPergunta").innerHTML = `<option value="">Todas as categorias</option>${opts}`;
    $("filtroCategoriaPergunta").value = currentFilter;
    $("perguntaCategoria").innerHTML = opts;
  }

  async function openCategoria(id=null) {
    try {
      const c = id ? await request(`/api/diagnostico/categorias/${id}`) : null;
      $("categoriaId").value = c?.id || "";
      $("categoriaNome").value = c?.nome || "";
      $("categoriaDescricao").value = c?.descricao || "";
      let proximaOrdem = 1;
      if (!c) {
        const ativas = await request("/api/diagnostico/categorias?ativo=true");
        const usadas = new Set(ativas.map(x=>Number(x.ordem)).filter(x=>Number.isInteger(x) && x>0));
        while (usadas.has(proximaOrdem)) proximaOrdem++;
      }
      $("categoriaOrdem").value = c?.ordem ?? proximaOrdem;
      $("categoriaAtiva").value = String(c?.ativo ?? true);
      $("tituloCategoria").textContent = c ? "Editar categoria" : "Nova categoria";
      $("dlgCategoria").showModal();
    } catch(e) { showMessage(e.message); }
  }

  async function toggleCategoria(id) {
    const c = state.categorias.find(x=>x.id===id);
    if (!c) return;
    try {
      if (c.ativo) await request(`/api/diagnostico/categorias/${id}`, {method:"DELETE"});
      else await request(`/api/diagnostico/categorias/${id}`, {method:"PUT", body:JSON.stringify({ativo:true})});
      showMessage(c.ativo ? "Categoria inativada." : "Categoria ativada.", "info");
      await loadCategorias();
    } catch(e) { showMessage(e.message); }
  }

  $("novaCategoria").onclick = () => openCategoria();
  $("buscaCategoria").oninput = renderCategorias;
  $("filtroCategoriaStatus").onchange = loadCategorias;
  $("formCategoria").addEventListener("submit", async e => {
    e.preventDefault();
    const id = $("categoriaId").value;
    const payload = {
      nome:$("categoriaNome").value.trim(),
      descricao:$("categoriaDescricao").value.trim() || null,
      ordem:Number($("categoriaOrdem").value || 0),
      ativo:$("categoriaAtiva").value === "true"
    };
    if (!id) payload.empresa_id = null;

    try {
      await request(id ? `/api/diagnostico/categorias/${id}` : "/api/diagnostico/categorias", {
        method:id ? "PUT" : "POST", body:JSON.stringify(payload)
      });
      $("dlgCategoria").close(); showMessage("Categoria salva.", "info"); await loadCategorias();
    } catch(e2) { showMessage(e2.message); }
  });

  async function loadPerguntas() {
    try {
      if (!state.categorias.length) {
        state.categorias = await request("/api/diagnostico/categorias?ativo=true");
        refreshCategoriaSelects();
      }
      const params = {
        categoria_id:$("filtroCategoriaPergunta").value,
        tipo_resposta:$("filtroTipoPergunta").value,
        natureza:$("filtroNaturezaPergunta").value,
        busca:$("buscaPergunta").value.trim() || null
      };
      state.perguntas = await request(`/api/diagnostico/perguntas${qs(params)}`);
      renderPerguntas();
    } catch(e) { showMessage(e.message); }
  }

  function renderPerguntas() {
    $("listaPerguntas").innerHTML = state.perguntas.length ? state.perguntas.map(p => `
      <article class="admin-item">
        <div class="admin-item-order">CÓDIGO<strong>${esc(p.codigo || "—")}</strong></div>
        <div>
          <h3>${esc(p.pergunta)}</h3>
          <p>${esc(state.categorias.find(c=>c.id===p.categoria_id)?.nome || "Categoria")}</p>
          <div class="admin-tags">
            <span class="admin-tag">${esc(p.tipo_resposta)}</span>
            <span class="admin-tag ${p.natureza==="AVALIATIVA" ? "eval" : ""}">${esc(p.natureza)}</span>
            <span class="admin-tag ${p.ativo ? "on" : "off"}">${p.ativo ? "Ativa" : "Inativa"}</span>
          </div>
        </div>
        <div class="admin-item-actions">
          <button type="button" data-edit-q="${p.id}">Editar</button>
          <button type="button" class="${p.ativo ? "danger" : ""}" data-toggle-q="${p.id}">${p.ativo ? "Inativar" : "Ativar"}</button>
        </div>
      </article>`).join("") : `<div class="admin-empty">Nenhuma pergunta encontrada.</div>`;
    $$("[data-edit-q]").forEach(b => b.onclick = () => openPergunta(b.dataset.editQ));
    $$("[data-toggle-q]").forEach(b => b.onclick = () => togglePergunta(b.dataset.toggleQ));
  }

  async function togglePergunta(id) {
    const p = state.perguntas.find(x=>x.id===id);
    try {
      if (p.ativo) await request(`/api/diagnostico/perguntas/${id}`, {method:"DELETE"});
      else await request(`/api/diagnostico/perguntas/${id}`, {method:"PUT",body:JSON.stringify({ativo:true})});
      showMessage(p.ativo ? "Pergunta inativada." : "Pergunta ativada.", "info");
      await loadPerguntas();
    } catch(e){showMessage(e.message)}
  }

  function addOptionRow(o={}) {
    const row = $("tplOpcao").content.firstElementChild.cloneNode(true);
    row.dataset.id = o.id || "";
    row.querySelector(".opt-rotulo").value = o.rotulo || "";
    row.querySelector(".opt-valor").value = o.valor || "";
    row.querySelector(".opt-estado").value = o.estado_interno || "";
    row.querySelector(".remove-option").onclick = () => {
      if (row.dataset.id) row.dataset.deleted = "true";
      row.classList.add("hidden");
    };
    row.addEventListener("dragstart",()=>row.classList.add("dragging"));
    row.addEventListener("dragend",()=>row.classList.remove("dragging"));
    row.addEventListener("dragover",e=>{e.preventDefault();row.classList.add("drag-over")});
    row.addEventListener("dragleave",()=>row.classList.remove("drag-over"));
    row.addEventListener("drop",e=>{
      e.preventDefault(); row.classList.remove("drag-over");
      const dragging = document.querySelector(".option-row.dragging");
      if (!dragging || dragging===row) return;
      const rect=row.getBoundingClientRect();
      $("listaOpcoes").insertBefore(dragging,e.clientY < rect.top+rect.height/2 ? row : row.nextSibling);
    });
    $("listaOpcoes").appendChild(row);
  }

  function addRangeRow(r={}) {
    const row=$("tplFaixa").content.firstElementChild.cloneNode(true);
    row.dataset.id=r.id||"";
    row.querySelector(".range-min").value=r.valor_min ?? "";
    row.querySelector(".range-max").value=r.valor_max ?? "";
    row.querySelector(".range-estado").value=r.estado_interno || "ALTO";
    row.querySelector(".remove-range").onclick=()=>{row.dataset.deleted="true";row.classList.add("hidden")};
    $("listaFaixas").appendChild(row);
  }

  function syncPerguntaUI() {
    const tipo=$("perguntaTipo").value;
    if (["MULTIPLA_ESCOLHA","TEXTO_CURTO"].includes(tipo)) {
      $("perguntaNatureza").value="CONTEXTO"; $("perguntaNatureza").disabled=true;
    } else $("perguntaNatureza").disabled=false;
    const natureza=$("perguntaNatureza").value;
    $("blocoAvaliacao").classList.toggle("hidden",natureza!=="AVALIATIVA");
    $("blocoOpcoes").classList.toggle("hidden",!["ESCOLHA_UNICA","MULTIPLA_ESCOLHA"].includes(tipo));
    $("blocoFaixas").classList.toggle("hidden",tipo!=="NUMERO");
    $$(".opt-estado").forEach(s=>{s.disabled=natureza!=="AVALIATIVA"; if(natureza!=="AVALIATIVA")s.value=""});
  }

  async function openPergunta(id=null, options={}) {
    state.perguntaReturnToBuilderModal = !!options.returnToBuilderModal;
    try {
      if (!state.categorias.length) {
        state.categorias=await request("/api/diagnostico/categorias?ativo=true"); refreshCategoriaSelects();
      }
      const p=id ? await request(`/api/diagnostico/perguntas/${id}`) : null;
      state.perguntaDetalhe=p;
      $("perguntaId").value=p?.id||"";
      $("perguntaCodigo").value=p?.codigo||"";
      $("perguntaCategoria").value=p?.categoria_id||options.categoria_id||state.categorias.find(c=>c.ativo)?.id||"";
      $("perguntaTexto").value=p?.pergunta||"";
      $("perguntaAjuda").value=p?.ajuda||"";
      $("perguntaTipo").value=p?.tipo_resposta||"ESCOLHA_UNICA";
      $("perguntaNatureza").value=p?.natureza||"AVALIATIVA";
      $("perguntaIdeal").value=p?.ideal||"";
      $("perguntaSugestao").value=p?.sugestao||"";
      $("perguntaAtiva").checked=p?.ativo ?? true;
      $("listaOpcoes").innerHTML=""; $("listaFaixas").innerHTML="";
      (p?.opcoes || [
        {valor:"SIM",rotulo:"Tenho e atende adequadamente",estado_interno:"ALTO"},
        {valor:"PARCIAL",rotulo:"Tenho, mas atende em partes",estado_interno:"MEDIO"},
        {valor:"NAO",rotulo:"Não tenho / não atende",estado_interno:"BAIXO"},
        {valor:"NA",rotulo:"Não se aplica ao meu negócio",estado_interno:"NA"},
        {valor:"NAO_SEI",rotulo:"Não sei informar",estado_interno:"NAO_SEI"}
      ]).forEach(addOptionRow);
      (p?.faixas||[]).forEach(addRangeRow);
      $("tituloPergunta").textContent=p?"Editar pergunta":"Nova pergunta";
      syncPerguntaUI();
      const congelada=!!p?.utilizada_em_resposta;
      ["perguntaCodigo","perguntaCategoria","perguntaTexto","perguntaAjuda","perguntaTipo","perguntaNatureza","perguntaIdeal","perguntaSugestao","perguntaAtiva","addOpcao","addFaixa"]
        .forEach(cid=>{const el=$(cid); if(el) el.disabled=congelada;});
      $$("#listaOpcoes input,#listaOpcoes select,#listaOpcoes button,#listaFaixas input,#listaFaixas select,#listaFaixas button").forEach(el=>el.disabled=congelada);
      const sb=$("#formPergunta button[type='submit']");
      if(sb){sb.disabled=congelada; sb.textContent=congelada?"Pergunta congelada":"Salvar";}
      $("dlgPergunta").showModal();
    } catch(e){showMessage(e.message)}
  }

  function collectOptions() {
    return $$("#listaOpcoes .option-row").map((row,i)=>({
      id:row.dataset.id||null, deleted:row.dataset.deleted==="true",
      valor:row.querySelector(".opt-valor").value.trim(), rotulo:row.querySelector(".opt-rotulo").value.trim(),
      estado_interno:$("perguntaNatureza").value==="AVALIATIVA" ? (row.querySelector(".opt-estado").value||null) : null,
      pontuacao:0, ordem:i+1, ativo:true
    }));
  }
  function collectRanges() {
    return $$("#listaFaixas .range-row").map(row=>({
      id:row.dataset.id||null, deleted:row.dataset.deleted==="true",
      valor_min:row.querySelector(".range-min").value===""?null:Number(row.querySelector(".range-min").value),
      valor_max:row.querySelector(".range-max").value===""?null:Number(row.querySelector(".range-max").value),
      estado_interno:row.querySelector(".range-estado").value
    }));
  }

  async function syncExistingOptions(perguntaId, original, current) {
    for (const o of current) {
      if (o.deleted) { if(o.id) await request(`/api/diagnostico/opcoes/${o.id}`,{method:"DELETE"}); continue; }
      const payload={valor:o.valor,rotulo:o.rotulo,estado_interno:o.estado_interno,pontuacao:0,ordem:o.ordem,ativo:true};
      if (o.id) await request(`/api/diagnostico/opcoes/${o.id}`,{method:"PUT",body:JSON.stringify(payload)});
      else await request(`/api/diagnostico/perguntas/${perguntaId}/opcoes`,{method:"POST",body:JSON.stringify(payload)});
    }
    const visibleIds=new Set(current.filter(x=>x.id&&!x.deleted).map(x=>x.id));
    for(const o of original||[]) if(!visibleIds.has(o.id) && !current.some(x=>x.id===o.id&&x.deleted)) {
      await request(`/api/diagnostico/opcoes/${o.id}`,{method:"DELETE"});
    }
  }

  async function syncExistingRanges(perguntaId, original, current) {
    for(const r of current){
      if(r.deleted){if(r.id)await request(`/api/diagnostico/faixas/${r.id}`,{method:"DELETE"});continue}
      const payload={valor_min:r.valor_min,valor_max:r.valor_max,estado_interno:r.estado_interno};
      if(r.id) await request(`/api/diagnostico/faixas/${r.id}`,{method:"PUT",body:JSON.stringify(payload)});
      else await request(`/api/diagnostico/perguntas/${perguntaId}/faixas`,{method:"POST",body:JSON.stringify(payload)});
    }
  }

  $("novaPergunta").onclick=()=>openPergunta();
  $("addOpcao").onclick=()=>{addOptionRow();syncPerguntaUI()};
  $("addFaixa").onclick=()=>addRangeRow();
  $("perguntaTipo").onchange=syncPerguntaUI;
  $("perguntaNatureza").onchange=syncPerguntaUI;
  ["filtroCategoriaPergunta","filtroTipoPergunta","filtroNaturezaPergunta"].forEach(id=>$(id).onchange=loadPerguntas);
  let buscaTimer;
  $("buscaPergunta").oninput=()=>{clearTimeout(buscaTimer);buscaTimer=setTimeout(loadPerguntas,300)};

  $("formPergunta").addEventListener("submit", async e=>{
    e.preventDefault();
    const id=$("perguntaId").value, tipo=$("perguntaTipo").value, natureza=$("perguntaNatureza").value;
    const options=collectOptions(), ranges=collectRanges();
    if(tipo==="ESCOLHA_UNICA" && natureza==="AVALIATIVA" && options.filter(x=>!x.deleted).some(x=>!x.estado_interno)){
      return showMessage("Toda opção de uma pergunta avaliativa precisa de interpretação.");
    }
    const base={
      categoria_id:$("perguntaCategoria").value,
      codigo:$("perguntaCodigo").value.trim()||null,
      pergunta:$("perguntaTexto").value.trim(),
      tipo_resposta:tipo,natureza,
      ideal:natureza==="AVALIATIVA"?$("perguntaIdeal").value.trim():null,
      sugestao:natureza==="AVALIATIVA"?$("perguntaSugestao").value.trim():null,
      ajuda:$("perguntaAjuda").value.trim()||null,
      ativo:$("perguntaAtiva").checked
    };
    try{
      if(!id){
        const payload={...base,empresa_id:null,
          opcoes:["ESCOLHA_UNICA","MULTIPLA_ESCOLHA"].includes(tipo)?options.filter(x=>!x.deleted).map(({id,deleted,...x})=>x):[],
          faixas:tipo==="NUMERO"?ranges.filter(x=>!x.deleted).map(({id,deleted,...x})=>x):[]
        };
        await request("/api/diagnostico/perguntas",{method:"POST",body:JSON.stringify(payload)});
      }else{
        const original=state.perguntaDetalhe||{};
        if(original.tipo_resposta!==tipo && ((original.opcoes||[]).length || (original.faixas||[]).length)){
          throw new Error("Para trocar o tipo de uma pergunta que já possui opções/faixas, remova primeiro as configurações existentes e salve.");
        }
        await request(`/api/diagnostico/perguntas/${id}`,{method:"PUT",body:JSON.stringify(base)});
        if(["ESCOLHA_UNICA","MULTIPLA_ESCOLHA"].includes(tipo))
          await syncExistingOptions(id,original.opcoes||[],options);
        if(tipo==="NUMERO") await syncExistingRanges(id,original.faixas||[],ranges);
      }
      $("dlgPergunta").close(); showMessage("Pergunta salva.","info"); await loadPerguntas();
      if(state.perguntaReturnToBuilderModal){await loadBuilderModalCatalogo(); state.perguntaReturnToBuilderModal=false;}
    }catch(err){showMessage(err.message)}
  });


  // ============================================================
  // FORMULÁRIOS / FORM BUILDER
  // ============================================================

  async function loadFormularios() {
    try {
      const ativo = $("filtroFormularioStatus").value;
      state.formularios = await request(`/api/diagnostico/formularios${qs({ativo})}`);
      renderFormularios();
    } catch (e) { showMessage(e.message); }
  }

  function renderFormularios() {
    const term = $("buscaFormulario").value.trim().toLowerCase();
    const list = state.formularios.filter(f =>
      !term ||
      (f.codigo || "").toLowerCase().includes(term) ||
      (f.nome || "").toLowerCase().includes(term)
    );

    $("listaFormularios").innerHTML = list.length ? list.map(f => `
      <article class="admin-item">
        <div class="admin-item-order">VERSÃO<strong>${f.versao}</strong></div>
        <div>
          <h3>${esc(f.nome)}</h3>
          <p>${esc(f.descricao || "Sem descrição")}</p>
          <div class="admin-tags">
            <span class="admin-tag">${esc(f.codigo)}</span>
            <span class="admin-tag">${esc(f.tipo)}</span>
            <span class="admin-tag ${f.ativo ? "on" : "off"}">${f.ativo ? "Ativo" : "Inativo"}</span>
            ${f.utilizado_em_diagnostico ? `<span class="admin-tag eval">Em uso / congelado</span>` : ""}
          </div>
        </div>
        <div class="admin-item-actions">
          <button type="button" data-build-form="${f.id}">Montar</button>
          <button type="button" data-version-form="${f.id}">Nova versão</button>
          <button type="button" data-clone-form="${f.id}">Clonar</button>
          <button type="button" data-edit-form="${f.id}">Editar</button>
          <button type="button" class="${f.ativo ? "danger" : ""}" data-toggle-form="${f.id}">${f.ativo ? "Inativar" : "Ativar"}</button>
        </div>
      </article>`).join("") : `<div class="admin-empty">Nenhum formulário encontrado.</div>`;

    $$("[data-build-form]").forEach(b => b.onclick = () => openBuilder(b.dataset.buildForm));
    $$("[data-version-form]").forEach(b => b.onclick = () => createNewVersion(b.dataset.versionForm));
    $$("[data-clone-form]").forEach(b => b.onclick = () => openCloneFormulario(b.dataset.cloneForm));
    $$("[data-edit-form]").forEach(b => b.onclick = () => openFormulario(b.dataset.editForm));
    $$("[data-toggle-form]").forEach(b => b.onclick = () => toggleFormulario(b.dataset.toggleForm));
  }

  async function openFormulario(id=null) {
    try {
      const f = id ? await request(`/api/diagnostico/formularios/${id}`) : null;
      $("formularioId").value = f?.id || "";
      $("formularioCodigo").value = f?.codigo || "";
      $("formularioCodigo").readOnly = !!f;
      $("formularioVersao").value = f?.versao ?? 1;
      $("formularioVersao").readOnly = true;
      $("formularioNome").value = f?.nome || "";
      $("formularioDescricao").value = f?.descricao || "";
      $("formularioTipo").value = f?.tipo || "TESTE";
      $("formularioAtivo").value = String(f?.ativo ?? true);
      if (!f) $("formularioCodigo").readOnly = false;
      $("tituloFormulario").textContent = f ? "Editar formulário" : "Novo formulário";
      $("dlgFormulario").showModal();
    } catch (e) { showMessage(e.message); }
  }

  async function createNewVersion(id) {
    try {
      const origem = await request(`/api/diagnostico/formularios/${id}`);
      if (!window.confirm(`Criar uma nova versão de "${origem.nome}"?\n\nA estrutura será copiada e a versão será incrementada automaticamente.`)) return;
      const nova = await request(`/api/diagnostico/formularios/${id}/nova-versao`, {
        method:"POST", body:JSON.stringify({ativo:true})
      });
      showMessage(`Nova versão v${nova.versao} criada.`, "info");
      await loadFormularios();
      await openBuilder(nova.id);
    } catch(e) { showMessage(e.message); }
  }

  async function toggleFormulario(id) {
    const f = state.formularios.find(x => x.id === id);
    if (!f) return;
    try {
      if (f.ativo) {
        await request(`/api/diagnostico/formularios/${id}`, {method:"DELETE"});
        showMessage("Formulário inativado.", "info");
      } else {
        await request(`/api/diagnostico/formularios/${id}`, {
          method:"PUT", body:JSON.stringify({ativo:true})
        });
        showMessage("Formulário ativado.", "info");
      }
      await loadFormularios();
    } catch (e) { showMessage(e.message); }
  }

  async function openCloneFormulario(id) {
    try {
      const f = await request(`/api/diagnostico/formularios/${id}`);
      state.cloneOrigem = f;
      $("cloneFormularioOrigemId").value = f.id;
      $("cloneOrigemInfo").textContent = `Origem: ${f.nome} — v${f.versao}. Perguntas e regras serão copiadas para um novo formulário.`;
      $("cloneCodigo").value = `${f.codigo}_COPIA`;
      $("cloneNome").value = `${f.nome} - Cópia`;
      $("cloneDescricao").value = f.descricao || "";
      $("cloneTipo").value = f.tipo || "TESTE";
      $("cloneVersao").value = 1;
      $("cloneAtivo").value = "true";
      $("dlgClonarFormulario").showModal();
    } catch (e) { showMessage(e.message); }
  }

  $("formClonarFormulario").addEventListener("submit", async e => {
    e.preventDefault();
    const origemId = $("cloneFormularioOrigemId").value;
    const payload = {
      codigo:$("cloneCodigo").value.trim(),
      nome:$("cloneNome").value.trim(),
      descricao:$("cloneDescricao").value.trim() || null,
      tipo:$("cloneTipo").value,
      versao:Number($("cloneVersao").value || 1),
      ativo:$("cloneAtivo").value === "true",
      empresa_id:state.cloneOrigem?.empresa_id || null
    };
    try {
      const clone = await request(`/api/diagnostico/formularios/${origemId}/clonar`, {
        method:"POST",
        body:JSON.stringify(payload)
      });
      $("dlgClonarFormulario").close();
      showMessage("Formulário clonado com perguntas e regras.", "info");
      await loadFormularios();
      await openBuilder(clone.id);
    } catch (err) { showMessage(err.message); }
  });

  $("novoFormulario").onclick = () => openFormulario();
  $("buscaFormulario").oninput = renderFormularios;
  $("filtroFormularioStatus").onchange = loadFormularios;

  $("formFormulario").addEventListener("submit", async e => {
    e.preventDefault();
    const id = $("formularioId").value;
    const payload = {
      nome:$("formularioNome").value.trim(),
      descricao:$("formularioDescricao").value.trim() || null,
      tipo:$("formularioTipo").value,
      ativo:$("formularioAtivo").value === "true"
    };
    if (!id) {
      payload.codigo = $("formularioCodigo").value.trim();
      payload.versao = 1;
      payload.empresa_id = null;
    }
    try {
      const saved = await request(
        id ? `/api/diagnostico/formularios/${id}` : "/api/diagnostico/formularios",
        {method:id ? "PUT" : "POST", body:JSON.stringify(payload)}
      );
      $("dlgFormulario").close();
      showMessage("Formulário salvo.", "info");
      await loadFormularios();
      if (!id) await openBuilder(saved.id);
    } catch (err) { showMessage(err.message); }
  });

  async function ensureCategoriasAtivas() {
    if (!state.categorias.length || !state.categorias.some(c => c.ativo)) {
      state.categorias = await request("/api/diagnostico/categorias?ativo=true");
    }
    const current = $("builderCategoria").value;
    $("builderCategoria").innerHTML =
      `<option value="">Todas as categorias</option>` +
      state.categorias.filter(c=>c.ativo).sort((a,b)=>a.ordem-b.ordem)
        .map(c=>`<option value="${c.id}">${esc(c.nome)}</option>`).join("");
    $("builderCategoria").value = current;
  }

  async function openBuilder(formularioId) {
    try {
      state.builderFormulario = await request(`/api/diagnostico/formularios/${formularioId}`);
      state.builderFrozen = !!state.builderFormulario.utilizado_em_diagnostico;
      state.builderPerguntas = state.builderFormulario.perguntas || [];
      state.builderRegras = state.builderFormulario.regras_exibicao || [];
      state.builderSelecionada = null;
      state.builderDetalhes = {};
      state.previewRespostas = {};
      await ensureCategoriasAtivas();
      await loadBuilderCatalogo();
      renderBuilder();
      showAdminView("builder");
    } catch (e) { showMessage(e.message); }
  }

  async function reloadBuilder() {
    if (!state.builderFormulario?.id) return;
    const f = await request(`/api/diagnostico/formularios/${state.builderFormulario.id}`);
    state.builderFormulario = f;
    state.builderPerguntas = f.perguntas || [];
    state.builderRegras = f.regras_exibicao || [];
    await loadBuilderCatalogo();
    renderBuilder();
  }

  async function loadBuilderCatalogo() {
    const params = {
      ativo:true,
      categoria_id:$("builderCategoria").value || null,
      natureza:$("builderNatureza").value || null,
      busca:$("builderBusca").value.trim() || null
    };
    state.builderCatalogo = await request(`/api/diagnostico/perguntas${qs(params)}`);
    renderBuilderCatalogo();
  }

  function renderBuilder() {
    const f = state.builderFormulario;
    if (!f) return;
    $("builderTitulo").textContent = `${f.nome} — v${f.versao}`;
    $("builderDescricao").textContent = f.descricao || `${f.codigo} • ${f.tipo}`;
    $("builderResumo").textContent = `${state.builderPerguntas.length} pergunta(s) • ${state.builderRegras.length} regra(s)` + (state.builderFrozen ? " • ESTRUTURA CONGELADA" : "");
    renderBuilderCatalogo();
    renderBuilderPerguntas();
    renderBuilderConfig();
  }

  function renderBuilderCatalogo() {
    const used = new Set(state.builderPerguntas.map(x=>x.pergunta_id));
    const box = $("builderCatalogo");
    box.innerHTML = "";
    if (!state.builderCatalogo.length) {
      box.innerHTML = `<div class="builder-empty">Nenhuma pergunta encontrada.</div>`;
      return;
    }

    state.builderCatalogo.forEach(q => {
      const item = document.createElement("article");
      const jaUsada = used.has(q.id);
      item.className = `builder-catalog-item${jaUsada ? " used" : ""}`;
      item.draggable = !jaUsada && !state.builderFrozen;
      item.dataset.id = q.id;
      item.innerHTML = `
        <div class="builder-drag">☰</div>
        <div class="builder-catalog-main">
          <span class="builder-code">${esc(q.codigo || "—")}</span>
          <span class="builder-qtext">${esc(q.pergunta)}</span>
          <span class="builder-meta">${esc(q.tipo_resposta)} • ${esc(q.natureza)}</span>
        </div>
        <span class="builder-used">${jaUsada ? "✓" : ""}</span>`;
      if (!jaUsada) {
        item.addEventListener("dragstart", e => {
          e.dataTransfer.setData("application/x-mdp-catalog", q.id);
          e.dataTransfer.effectAllowed = "copy";
        });
      }
      box.appendChild(item);
    });
  }

  function builderRulesBySource(sourceId) {
    return state.builderRegras.filter(r => r.pergunta_origem_id === sourceId);
  }

  function renderBuilderPerguntas() {
    const box = $("builderFormDrop");
    box.innerHTML = "";

    if (!state.builderPerguntas.length) {
      box.innerHTML = `<div class="builder-empty">Arraste perguntas do catálogo para cá.</div>`;
      return;
    }

    state.builderPerguntas.forEach((fp, idx) => {
      const item = document.createElement("article");
      item.className = `builder-form-item${state.builderSelecionada === fp.pergunta_id ? " selected" : ""}`;
      item.draggable = !state.builderFrozen;
      item.dataset.id = fp.pergunta_id;

      const rules = builderRulesBySource(fp.pergunta_id);
      const ruleSummary = {};
      rules.forEach(r => ruleSummary[r.opcao_origem_id] = (ruleSummary[r.opcao_origem_id] || 0) + 1);

      item.innerHTML = `
        <div class="builder-drag">☰</div>
        <div class="builder-order">${String(idx + 1).padStart(2,"0")}</div>
        <div class="builder-form-main">
          <span class="builder-code">${esc(fp.codigo || "—")}</span>
          <span class="builder-qtext">${esc(fp.pergunta)}</span>
          <span class="builder-meta">${esc(fp.categoria_nome)} • ${esc(fp.tipo_resposta)} • ${esc(fp.natureza)}${fp.obrigatoria ? " • Obrigatória" : ""}</span>
          <div class="builder-rule-chips">${Object.values(ruleSummary).map(n=>`<span class="builder-rule-chip">${n} regra(s)</span>`).join("")}</div>
        </div>
        <button type="button" class="builder-remove" title="Remover do formulário">×</button>`;

      const removeBtn = item.querySelector(".builder-remove");
      removeBtn.disabled = state.builderFrozen;
      removeBtn.onclick = e => {
        e.stopPropagation();
        if (!state.builderFrozen) removeBuilderPergunta(fp.pergunta_id);
      };
      item.onclick = () => selectBuilderPergunta(fp.pergunta_id);

      item.addEventListener("dragstart", e => {
        e.dataTransfer.setData("application/x-mdp-form", fp.pergunta_id);
        e.dataTransfer.effectAllowed = "move";
      });
      item.addEventListener("dragover", e => e.preventDefault());
      item.addEventListener("drop", async e => {
        e.preventDefault();
        e.stopPropagation();
        const moving = e.dataTransfer.getData("application/x-mdp-form");
        if (!moving || moving === fp.pergunta_id) return;
        const ids = state.builderPerguntas.map(x=>x.pergunta_id);
        const from = ids.indexOf(moving);
        const to = ids.indexOf(fp.pergunta_id);
        if (from < 0 || to < 0) return;
        ids.splice(from,1);
        ids.splice(to,0,moving);
        await saveBuilderOrder(ids);
      });
      box.appendChild(item);
    });
  }

  $("builderFormDrop").addEventListener("dragover", e => {
    e.preventDefault();
    $("builderFormDrop").classList.add("drag-over");
  });
  $("builderFormDrop").addEventListener("dragleave", () => $("builderFormDrop").classList.remove("drag-over"));
  $("builderFormDrop").addEventListener("drop", async e => {
    e.preventDefault();
    $("builderFormDrop").classList.remove("drag-over");
    const catalogId = e.dataTransfer.getData("application/x-mdp-catalog");
    if (!catalogId) return;
    await addBuilderPergunta(catalogId);
  });

  async function addBuilderPergunta(perguntaId) {
    try {
      const ordem = state.builderPerguntas.length + 1;
      await request(`/api/diagnostico/formularios/${state.builderFormulario.id}/perguntas`, {
        method:"POST",
        body:JSON.stringify({pergunta_id:perguntaId, ordem, obrigatoria:false, ativo:true})
      });
      showMessage("Pergunta adicionada ao formulário.", "info");
      await reloadBuilder();
    } catch (e) { showMessage(e.message); }
  }

  async function removeBuilderPergunta(perguntaId) {
    try {
      await request(`/api/diagnostico/formularios/${state.builderFormulario.id}/perguntas/${perguntaId}`, {
        method:"DELETE"
      });
      if (state.builderSelecionada === perguntaId) state.builderSelecionada = null;
      showMessage("Pergunta removida do formulário.", "info");
      await reloadBuilder();
    } catch (e) { showMessage(e.message); }
  }

  async function saveBuilderOrder(ids) {
    try {
      await request(`/api/diagnostico/formularios/${state.builderFormulario.id}/perguntas/ordenacao`, {
        method:"PUT",
        body:JSON.stringify({itens:ids.map((pergunta_id,i)=>({pergunta_id, ordem:i+1}))})
      });
      await reloadBuilder();
    } catch (e) { showMessage(e.message); }
  }

  async function selectBuilderPergunta(perguntaId) {
    state.builderSelecionada = perguntaId;
    if (!state.builderDetalhes[perguntaId]) {
      try {
        state.builderDetalhes[perguntaId] = await request(`/api/diagnostico/perguntas/${perguntaId}`);
      } catch (e) { showMessage(e.message); return; }
    }
    renderBuilderPerguntas();
    renderBuilderConfig();
  }

  async function setBuilderObrigatoria(value) {
    if (!state.builderSelecionada) return;
    try {
      await request(`/api/diagnostico/formularios/${state.builderFormulario.id}/perguntas/${state.builderSelecionada}`, {
        method:"PUT",
        body:JSON.stringify({obrigatoria:value})
      });
      const fp = state.builderPerguntas.find(x=>x.pergunta_id===state.builderSelecionada);
      if (fp) fp.obrigatoria = value;
      renderBuilderPerguntas();
      showMessage("Configuração atualizada.", "info");
    } catch (e) { showMessage(e.message); }
  }

  $("builderCfgObrigatoria").onchange = e => setBuilderObrigatoria(e.target.checked);

  function renderBuilderConfig() {
    const id = state.builderSelecionada;
    $("builderConfigVazio").classList.toggle("hidden", !!id);
    $("builderConfig").classList.toggle("hidden", !id);
    if (!id) return;

    const fp = state.builderPerguntas.find(x=>x.pergunta_id===id);
    const q = state.builderDetalhes[id];

    $("builderCfgCodigo").textContent = fp?.codigo || q?.codigo || "—";
    $("builderCfgPergunta").textContent = fp?.pergunta || q?.pergunta || "";
    $("builderCfgMeta").textContent = `${fp?.categoria_nome || ""} • ${fp?.tipo_resposta || ""} • ${fp?.natureza || ""}`;
    $("builderCfgObrigatoria").checked = !!fp?.obrigatoria;
    $("builderCfgObrigatoria").disabled = state.builderFrozen;

    const options = q?.opcoes || [];
    $("builderRulesBlock").classList.toggle("hidden", !options.length);
    $("builderNoRules").classList.toggle("hidden", !!options.length);
    if (!options.length) return;

    const editor = $("builderRulesEditor");
    editor.innerHTML = "";

    options.filter(o=>o.ativo !== false).forEach(opt => {
      const rules = state.builderRegras.filter(
        r => r.pergunta_origem_id === id && r.opcao_origem_id === opt.id
      );
      const wrap = document.createElement("div");
      wrap.className = "builder-rule-option";
      wrap.innerHTML = `
        <div class="builder-rule-head">
          <strong>${esc(opt.rotulo)}</strong>
          <span class="builder-inline-status">${rules.length} destino(s)</span>
        </div>
        <div class="builder-rule-body">
          <div class="builder-target-list"></div>
          <button type="button" class="builder-add-target">+ Adicionar pergunta</button>
          <div class="builder-picker hidden"></div>
        </div>`;

      const list = wrap.querySelector(".builder-target-list");
      rules.forEach(rule => {
        const dest = state.builderPerguntas.find(x=>x.pergunta_id===rule.pergunta_destino_id);
        const row = document.createElement("div");
        row.className = "builder-target";
        row.innerHTML = `<span><b>${esc(dest?.codigo || "—")}</b> — ${esc(dest?.pergunta || rule.pergunta_destino_id)}</span><button type="button" title="Remover regra">×</button>`;
        row.querySelector("button").onclick = () => deleteBuilderRule(rule.id);
        list.appendChild(row);
      });

      const addTargetBtn = wrap.querySelector(".builder-add-target");
      addTargetBtn.disabled = state.builderFrozen;
      addTargetBtn.onclick = () => {
        if (!state.builderFrozen) openBuilderModal(id, opt.id, opt.rotulo);
      };
      editor.appendChild(wrap);
    });
  }


  function builderAdjacency(extraEdge=null) {
    const adj = new Map();
    state.builderRegras.forEach(r => {
      if (!adj.has(r.pergunta_origem_id)) adj.set(r.pergunta_origem_id, new Set());
      adj.get(r.pergunta_origem_id).add(r.pergunta_destino_id);
    });
    if (extraEdge) {
      const [a,b] = extraEdge;
      if (!adj.has(a)) adj.set(a, new Set());
      adj.get(a).add(b);
    }
    return adj;
  }

  function builderWouldCreateCycle(sourceId, targetId) {
    if (sourceId === targetId) return true;
    const adj = builderAdjacency([sourceId,targetId]);
    const stack = [targetId];
    const visited = new Set();
    while (stack.length) {
      const current = stack.pop();
      if (current === sourceId) return true;
      if (visited.has(current)) continue;
      visited.add(current);
      (adj.get(current) || new Set()).forEach(n => stack.push(n));
    }
    return false;
  }

  async function openBuilderModal(sourceId, optionId, optionLabel) {
    state.builderModalSourceId = sourceId;
    state.builderModalOptionId = optionId;
    state.builderModalSelected = new Set();

    const source = state.builderPerguntas.find(x=>x.pergunta_id===sourceId);
    $("builderModalContexto").textContent =
      `Quando “${optionLabel}” for selecionado em ${source?.codigo || "esta pergunta"}, mostrar:`;

    const cats = state.categorias.filter(c=>c.ativo).sort((a,b)=>a.ordem-b.ordem);
    $("builderModalCategoria").innerHTML =
      `<option value="">Todas as categorias</option>` +
      cats.map(c=>`<option value="${c.id}">${esc(c.nome)}</option>`).join("");

    $("builderModalCategoria").value = "";
    $("builderModalNatureza").value = "";
    $("builderModalTipo").value = "";
    $("builderModalDisponibilidade").value = "";
    $("builderModalBusca").value = "";

    await loadBuilderModalCatalogo();
    $("dlgBuilderSelecionarPerguntas").showModal();
  }

  async function loadBuilderModalCatalogo() {
    try {
      const params = {
        ativo:true,
        categoria_id:$("builderModalCategoria").value || null,
        natureza:$("builderModalNatureza").value || null,
        tipo_resposta:$("builderModalTipo").value || null,
        busca:$("builderModalBusca").value.trim() || null
      };
      state.builderModalCatalogo = await request(`/api/diagnostico/perguntas${qs(params)}`);
      renderBuilderModalCatalogo();
    } catch (e) { showMessage(e.message); }
  }

  function renderBuilderModalCatalogo() {
    const sourceId = state.builderModalSourceId;
    const optionId = state.builderModalOptionId;
    const inForm = new Set(state.builderPerguntas.filter(x=>x.ativo).map(x=>x.pergunta_id));
    const existing = new Set(
      state.builderRegras
        .filter(r=>r.pergunta_origem_id===sourceId && r.opcao_origem_id===optionId)
        .map(r=>r.pergunta_destino_id)
    );
    const availability = $("builderModalDisponibilidade").value;

    const rows = state.builderModalCatalogo.filter(q => {
      const inside = inForm.has(q.id);
      if (availability === "NO_FORMULARIO" && !inside) return false;
      if (availability === "FORA_FORMULARIO" && inside) return false;
      return !existing.has(q.id);
    });

    const box = $("builderModalLista");
    box.innerHTML = "";
    if (!rows.length) {
      box.innerHTML = `<div class="builder-empty">Nenhuma pergunta disponível para este filtro.</div>`;
      updateBuilderModalSelectedCount();
      return;
    }

    rows.forEach(q => {
      const inside = inForm.has(q.id);
      const blocked = builderWouldCreateCycle(sourceId, q.id);
      const item = document.createElement("label");
      item.className = `builder-modal-item${blocked ? " blocked" : ""}`;
      item.innerHTML = `
        <input type="checkbox" value="${q.id}" ${blocked ? "disabled" : ""} ${state.builderModalSelected.has(q.id) ? "checked" : ""}>
        <span class="builder-modal-item-main">
          <span class="builder-code">${esc(q.codigo || "—")}</span>
          <span class="builder-qtext">${esc(q.pergunta)}</span>
          <span class="builder-meta">${esc(q.tipo_resposta)} • ${esc(q.natureza)}</span>
          ${blocked ? `<span class="builder-modal-loop-reason">🔒 Esta relação criaria dependência circular.</span>` : ""}
        </span>
        <span class="builder-modal-item-actions">
          <button type="button" class="builder-modal-edit">✏ Editar</button>
          <span class="builder-modal-item-status ${blocked ? "block" : inside ? "in" : "out"}">
            ${blocked ? "Bloqueada" : inside ? "✓ no formulário" : "＋ adicionar"}
          </span>
        </span>`;

      item.querySelector(".builder-modal-edit").onclick=async ev=>{
        ev.preventDefault(); ev.stopPropagation();
        const d=await request(`/api/diagnostico/perguntas/${q.id}`);
        if(d.utilizada_em_resposta){showMessage("Pergunta já utilizada: está congelada. Crie uma nova pergunta."); return;}
        openPergunta(q.id,{returnToBuilderModal:true});
      };
      const cb = item.querySelector("input");
      if (!blocked) {
        cb.onchange = () => {
          cb.checked ? state.builderModalSelected.add(q.id) : state.builderModalSelected.delete(q.id);
          updateBuilderModalSelectedCount();
        };
      }
      box.appendChild(item);
    });
    updateBuilderModalSelectedCount();
  }

  function updateBuilderModalSelectedCount() {
    $("builderModalSelecionadas").textContent = `${state.builderModalSelected.size} selecionada(s)`;
  }

  async function ensureBuilderQuestionInForm(perguntaId) {
    const exists = state.builderPerguntas.some(x=>x.pergunta_id===perguntaId && x.ativo);
    if (exists) return;

    await request(`/api/diagnostico/formularios/${state.builderFormulario.id}/perguntas`, {
      method:"POST",
      body:JSON.stringify({
        pergunta_id:perguntaId,
        ordem:state.builderPerguntas.length + 1,
        obrigatoria:false,
        ativo:true
      })
    });

    // Atualiza imediatamente para que a API de regra encontre a associação ativa.
    const fresh = await request(`/api/diagnostico/formularios/${state.builderFormulario.id}`);
    state.builderFormulario = fresh;
    state.builderPerguntas = fresh.perguntas || [];
    state.builderRegras = fresh.regras_exibicao || [];
  }

  $("formBuilderSelecionarPerguntas").addEventListener("submit", async e => {
    e.preventDefault();
    const sourceId = state.builderModalSourceId;
    const optionId = state.builderModalOptionId;
    const selected = [...state.builderModalSelected];
    if (!selected.length) return;

    try {
      // Segunda validação no frontend imediatamente antes de persistir.
      const invalid = selected.find(id=>builderWouldCreateCycle(sourceId,id));
      if (invalid) throw new Error("Uma das relações selecionadas criaria dependência circular.");

      for (const targetId of selected) {
        await ensureBuilderQuestionInForm(targetId);
        await createBuilderRule(sourceId, optionId, targetId);
      }

      $("dlgBuilderSelecionarPerguntas").close();
      showMessage("Perguntas condicionais adicionadas.", "info");
      await reloadBuilder();
      state.builderSelecionada = sourceId;
      if (!state.builderDetalhes[sourceId]) {
        state.builderDetalhes[sourceId] = await request(`/api/diagnostico/perguntas/${sourceId}`);
      }
      renderBuilder();
    } catch (err) { showMessage(err.message); }
  });

  $("builderModalNovaPergunta").onclick=()=>openPergunta(null,{
    returnToBuilderModal:true,
    categoria_id:$("builderModalCategoria").value||null
  });

  ["builderModalCategoria","builderModalNatureza","builderModalTipo","builderModalDisponibilidade"]
    .forEach(id => $(id).onchange = loadBuilderModalCatalogo);

  $("builderModalBusca").oninput = () => {
    window.clearTimeout($("builderModalBusca")._timer);
    $("builderModalBusca")._timer = window.setTimeout(loadBuilderModalCatalogo,250);
  };

  async function createBuilderRule(pergunta_origem_id, opcao_origem_id, pergunta_destino_id) {
    try {
      await request(`/api/diagnostico/formularios/${state.builderFormulario.id}/regras-exibicao`, {
        method:"POST",
        body:JSON.stringify({pergunta_origem_id, opcao_origem_id, pergunta_destino_id})
      });
    } catch (e) {
      showMessage(e.message);
      throw e;
    }
  }

  async function deleteBuilderRule(regraId) {
    try {
      await request(`/api/diagnostico/regras-exibicao/${regraId}`, {method:"DELETE"});
      showMessage("Regra removida.", "info");
      await reloadBuilder();
    } catch (e) { showMessage(e.message); }
  }

  $("builderBusca").oninput = () => {
    window.clearTimeout($("builderBusca")._timer);
    $("builderBusca")._timer = window.setTimeout(loadBuilderCatalogo, 250);
  };
  $("builderCategoria").onchange = loadBuilderCatalogo;
  $("builderNatureza").onchange = loadBuilderCatalogo;
  $("voltarFormularios").onclick = () => showAdminView("formularios");

  // ============================================================
  // PREVIEW REAL DO MODELO (sem criar diagnóstico)
  // ============================================================

  async function loadPreviewDetails() {
    const ids = state.builderPerguntas.map(x=>x.pergunta_id);
    await Promise.all(ids.map(async id => {
      if (!state.builderDetalhes[id]) {
        state.builderDetalhes[id] = await request(`/api/diagnostico/perguntas/${id}`);
      }
    }));
  }

  function previewTargetsSet() {
    return new Set(state.builderRegras.map(r=>r.pergunta_destino_id));
  }

  function computePreviewVisible() {
    const visible = new Set();
    const targets = previewTargetsSet();

    state.builderPerguntas.filter(fp=>fp.ativo).forEach(fp => {
      if (!targets.has(fp.pergunta_id)) visible.add(fp.pergunta_id);
    });

    let changed = true;
    while (changed) {
      changed = false;
      [...visible].forEach(sourceId => {
        const answer = state.previewRespostas[sourceId];
        if (answer === undefined || answer === null) return;
        const selected = Array.isArray(answer) ? answer : [answer];
        selected.forEach(optionId => {
          state.builderRegras
            .filter(r=>r.pergunta_origem_id===sourceId && r.opcao_origem_id===optionId)
            .forEach(r=>{
              if (!visible.has(r.pergunta_destino_id)) {
                visible.add(r.pergunta_destino_id);
                changed = true;
              }
            });
        });
      });
    }
    return visible;
  }

  function cleanupHiddenPreviewAnswers(visible) {
    Object.keys(state.previewRespostas).forEach(id => {
      if (!visible.has(id)) delete state.previewRespostas[id];
    });
  }

  function previewAnswered(id) {
    const a = state.previewRespostas[id];
    if (Array.isArray(a)) return a.length > 0;
    return a !== undefined && a !== null && String(a).trim() !== "";
  }

  function renderPreview() {
    const visible = computePreviewVisible();
    cleanupHiddenPreviewAnswers(visible);
    const ordered = state.builderPerguntas.filter(fp=>fp.ativo && visible.has(fp.pergunta_id));
    const answered = ordered.filter(fp=>previewAnswered(fp.pergunta_id)).length;
    $("previewProgresso").textContent = `${answered} de ${ordered.length} respondida(s)`;
    $("previewTitulo").textContent = `${state.builderFormulario.nome} — v${state.builderFormulario.versao}`;

    const box = $("previewConteudo");
    box.innerHTML = "";

    if (!ordered.length) {
      box.innerHTML = `<div class="builder-empty">Nenhuma pergunta aplicável.</div>`;
      return;
    }

    ordered.forEach(fp => {
      const q = state.builderDetalhes[fp.pergunta_id];
      if (!q) return;

      const section = document.createElement("section");
      section.className = "builder-preview-question";
      section.innerHTML = `
        <div class="builder-preview-section">${esc(fp.categoria_nome)} • ${esc(fp.codigo || "—")}${fp.obrigatoria ? " • obrigatória" : ""}</div>
        <h3>${esc(q.pergunta)}</h3>
        <div class="builder-preview-options"></div>`;

      const opts = section.querySelector(".builder-preview-options");

      if (q.tipo_resposta === "MULTIPLA_ESCOLHA") {
        (q.opcoes || []).filter(o=>o.ativo !== false).forEach(o => {
          const label = document.createElement("label");
          const checked = (state.previewRespostas[q.id] || []).includes(o.id);
          label.innerHTML = `<input type="checkbox" ${checked ? "checked" : ""}><span>${esc(o.rotulo)}</span>`;
          label.querySelector("input").onchange = e => {
            const set = new Set(state.previewRespostas[q.id] || []);
            e.target.checked ? set.add(o.id) : set.delete(o.id);
            state.previewRespostas[q.id] = [...set];
            renderPreview();
          };
          opts.appendChild(label);
        });
      } else if (q.tipo_resposta === "ESCOLHA_UNICA") {
        (q.opcoes || []).filter(o=>o.ativo !== false).forEach(o => {
          const label = document.createElement("label");
          const checked = state.previewRespostas[q.id] === o.id;
          label.innerHTML = `<input type="radio" name="pv_${q.id}" ${checked ? "checked" : ""}><span>${esc(o.rotulo)}</span>`;
          label.querySelector("input").onchange = () => {
            state.previewRespostas[q.id] = o.id;
            renderPreview();
          };
          opts.appendChild(label);
        });
      } else if (q.tipo_resposta === "TEXTO_CURTO") {
        const input = document.createElement("input");
        input.placeholder = "Digite sua resposta...";
        input.value = state.previewRespostas[q.id] || "";
        input.oninput = e => {
          state.previewRespostas[q.id] = e.target.value;
          const vis = computePreviewVisible();
          const ord = state.builderPerguntas.filter(x=>x.ativo && vis.has(x.pergunta_id));
          $("previewProgresso").textContent = `${ord.filter(x=>previewAnswered(x.pergunta_id)).length} de ${ord.length} respondida(s)`;
        };
        opts.appendChild(input);
      } else if (q.tipo_resposta === "NUMERO") {
        const input = document.createElement("input");
        input.type = "number";
        input.step = "any";
        input.placeholder = "Informe um número";
        input.value = state.previewRespostas[q.id] ?? "";
        input.oninput = e => {
          state.previewRespostas[q.id] = e.target.value;
          const vis = computePreviewVisible();
          const ord = state.builderPerguntas.filter(x=>x.ativo && vis.has(x.pergunta_id));
          $("previewProgresso").textContent = `${ord.filter(x=>previewAnswered(x.pergunta_id)).length} de ${ord.length} respondida(s)`;
        };
        opts.appendChild(input);
      }

      box.appendChild(section);
    });
  }

  $("abrirPreview").onclick = async () => {
    try {
      await loadPreviewDetails();
      state.previewRespostas = {};
      showAdminView("builderPreview");
      renderPreview();
    } catch (e) { showMessage(e.message); }
  };

  $("voltarBuilder").onclick = () => {
    showAdminView("builder");
    renderBuilder();
  };

  // Em DEV_AUTH local, /api/auth/me funciona sem token e abre o Admin diretamente.
  // Em produção a chamada retorna 401 e a tela de login permanece normal.
  loadMe().catch(() => {});

  // Evita submissão acidental dos dialogs por botões auxiliares.
  $$("dialog button").forEach(b=>{ if(!b.getAttribute("type")) b.setAttribute("type","button"); });
})();