/* MDP Omni - area do tenant (Integrations, Inbox, Comments). Sem dependencias.
   - Sessao somente em memoria (recarregar a pagina exige novo login), como o backoffice atual.
   - Todo texto vindo de terceiros (mensagens, comentarios) e inserido com textContent: nunca innerHTML. */
(function () {
  "use strict";

  var SITE = "https://mdpconsultoria.com.br";
  var LEGAL_BY_LANG = {
    pt: { privacy: SITE + "/politica-de-privacidade.html", terms: SITE + "/termos-de-servico.html", deletion: SITE + "/politica-de-privacidade.html#exclusao-de-dados" },
    en: { privacy: SITE + "/privacy-policy-en.html", terms: SITE + "/terms-of-service-en.html", deletion: SITE + "/privacy-policy-en.html#data-deletion" }
  };
  /* os links legais acompanham o idioma da tela (as paginas em ingles existem no site) */
  function legal() { return LEGAL_BY_LANG[state.lang] || LEGAL_BY_LANG.en; }
  var POLL_MS = 10000;

  var I18N = {
    en: {
      signin: "Sign in", signin_sub: "Use your email and password to access your workspace.", email: "Email", password: "Password",
      email_ph: "you@company.com", password_ph: "Your password", signing_in: "Signing in…", signout: "Sign out",
      mfa_title: "Verification code", mfa_sub: "Enter the 6-digit code from your authenticator app.", mfa_code: "Code", verify: "Verify", back: "Back",
      privacy: "Privacy Policy", terms: "Terms of Service", deletion: "Data deletion", workspace: "Workspace",
      tab_integrations: "Integrations", tab_inbox: "Inbox", tab_comments: "Comments",
      err_credentials: "Invalid email or password.", err_locked: "Too many attempts. Try again in a few minutes.", err_expired: "This access has expired.",
      err_noaccess: "This account does not have access to this workspace.", err_mfa_setup: "This account must set up multi-factor authentication first. Please sign in at /login.",
      err_email: "Enter a valid email address.", err_network: "Could not reach the server. Please try again.", err_generic: "Something went wrong. Please try again.",
      err_mfa_code: "Invalid verification code.", session_expired: "Your session expired. Please sign in again.",
      no_omni: "Your account does not have access to MDP Omni.",
      int_title: "Integrations", int_lead: "Connect your Instagram and Facebook accounts to receive messages and comments in one place, and reply from here.",
      instagram: "Instagram", facebook_page: "Facebook Page", messenger: "Messenger",
      st_NOT_CONNECTED: "Not connected", st_CONNECTED: "Connected", st_PENDENTE: "Pending", st_EXPIRANDO: "Expiring soon", st_EXPIRADO: "Expired", st_REVOGADO: "Disconnected", st_ERRO: "Error",
      ig_desc: "Receive direct messages and comments on your posts, and reply from MDP Omni. You will sign in with Instagram.",
      fb_desc: "Receive Messenger conversations and comments on your Page's posts, and reply from MDP Omni. You will sign in with Facebook and choose which Page to connect.",
      connect_ig: "Connect Instagram", connect_fb: "Connect Facebook Page", reconnect: "Reconnect", disconnect: "Disconnect",
      access_granted: "Access granted", ig_scopes: "profile, direct messages, comments", fb_scopes: "Page list, messages, comments", connection: "Connection", renews: "renews automatically",
      you_choose: "You choose", you_choose_v: "the account and what to share", control: "You stay in control", control_v: "disconnect at any time",
      int_foot: "Disconnecting a channel stops message sync and revokes this app's access to the account.", request_deletion: "Request data deletion",
      not_enabled: "Connecting channels is not enabled yet.", disc_not_enabled: "Disconnecting channels is not enabled yet.",
      inbox: "Inbox", all: "All", loading: "Loading…", no_convs: "No conversations yet.", pick_conv: "Select a conversation to read and reply.",
      via_ig: "via Instagram direct message", via_fb: "via Messenger", window_open: "24-hour reply window open", window_closed: "24-hour reply window closed",
      reply_ph: "Write a reply…", send: "Send", sending: "Sending…", closed_note: "You can reply again after the customer writes to you.",
      sent_ok: "Sent from MDP Omni · Delivered", not_sent: "Not sent: channel not connected", not_sent_gen: "Not sent", saved_not_sent: "Saved, but not sent: this channel is not connected yet.",
      comments: "Comments", no_comments: "No comments yet.", on_post: "On post", reply: "Reply", replied: "Replied", reply_to: "Reply to ", cancel: "Cancel",
      sent_by: "Sent from MDP Omni", err_window: "The 24-hour reply window is closed.", err_empty: "Write a message first.", now: "now"
    },
    pt: {
      signin: "Entrar", signin_sub: "Use seu e-mail e senha para acessar seu workspace.", email: "E-mail", password: "Senha",
      email_ph: "voce@empresa.com", password_ph: "Sua senha", signing_in: "Entrando…", signout: "Sair",
      mfa_title: "Código de verificação", mfa_sub: "Digite o código de 6 dígitos do seu app autenticador.", mfa_code: "Código", verify: "Verificar", back: "Voltar",
      privacy: "Política de Privacidade", terms: "Termos de Serviço", deletion: "Exclusão de dados", workspace: "Workspace",
      tab_integrations: "Integrações", tab_inbox: "Caixa de entrada", tab_comments: "Comentários",
      err_credentials: "E-mail ou senha inválidos.", err_locked: "Muitas tentativas. Tente novamente em alguns minutos.", err_expired: "Este acesso expirou.",
      err_noaccess: "Esta conta não tem acesso a este workspace.", err_mfa_setup: "Esta conta precisa configurar a autenticação em duas etapas antes. Entre em /login.",
      err_email: "Informe um e-mail válido.", err_network: "Não foi possível falar com o servidor. Tente novamente.", err_generic: "Algo deu errado. Tente novamente.",
      err_mfa_code: "Código de verificação inválido.", session_expired: "Sua sessão expirou. Entre novamente.",
      no_omni: "Sua conta não tem acesso ao MDP Omni.",
      int_title: "Integrações", int_lead: "Conecte suas contas do Instagram e do Facebook para receber mensagens e comentários em um só lugar e responder por aqui.",
      instagram: "Instagram", facebook_page: "Página do Facebook", messenger: "Messenger",
      st_NOT_CONNECTED: "Não conectado", st_CONNECTED: "Conectado", st_PENDENTE: "Pendente", st_EXPIRANDO: "Expirando", st_EXPIRADO: "Expirado", st_REVOGADO: "Desconectado", st_ERRO: "Erro",
      ig_desc: "Receba mensagens diretas e comentários dos seus posts e responda pelo MDP Omni. Você entrará com o Instagram.",
      fb_desc: "Receba conversas do Messenger e comentários nos posts da sua Página e responda pelo MDP Omni. Você entrará com o Facebook e escolherá qual Página conectar.",
      connect_ig: "Conectar Instagram", connect_fb: "Conectar Página do Facebook", reconnect: "Reconectar", disconnect: "Desconectar",
      access_granted: "Acesso concedido", ig_scopes: "perfil, mensagens diretas, comentários", fb_scopes: "lista de Páginas, mensagens, comentários", connection: "Conexão", renews: "renova automaticamente",
      you_choose: "Você escolhe", you_choose_v: "a conta e o que compartilhar", control: "Você no controle", control_v: "desconecte quando quiser",
      int_foot: "Desconectar um canal interrompe a sincronização de mensagens e revoga o acesso deste app à conta.", request_deletion: "Solicitar exclusão de dados",
      not_enabled: "A conexão de canais ainda não está habilitada.", disc_not_enabled: "A desconexão de canais ainda não está habilitada.",
      inbox: "Caixa de entrada", all: "Todas", loading: "Carregando…", no_convs: "Nenhuma conversa ainda.", pick_conv: "Selecione uma conversa para ler e responder.",
      via_ig: "via mensagem direta do Instagram", via_fb: "via Messenger", window_open: "Janela de resposta de 24h aberta", window_closed: "Janela de resposta de 24h fechada",
      reply_ph: "Escreva uma resposta…", send: "Enviar", sending: "Enviando…", closed_note: "Você poderá responder de novo depois que o cliente escrever.",
      sent_ok: "Enviado pelo MDP Omni · Entregue", not_sent: "Não enviado: canal não conectado", not_sent_gen: "Não enviado", saved_not_sent: "Salvo, mas não enviado: este canal ainda não está conectado.",
      comments: "Comentários", no_comments: "Nenhum comentário ainda.", on_post: "No post", reply: "Responder", replied: "Respondido", reply_to: "Responder a ", cancel: "Cancelar",
      sent_by: "Enviado pelo MDP Omni", err_window: "A janela de resposta de 24h está fechada.", err_empty: "Escreva uma mensagem primeiro.", now: "agora"
    }
  };

  var state = { lang: "en", access: null, refresh: null, me: null, tab: null, poll: null, refreshing: null, inbox: { channel: null, selected: null }, comments: { channel: null } };
  try { var saved = localStorage.getItem("mdp_omni_lang"); if (saved === "pt" || saved === "en") state.lang = saved; } catch (e) { /* ignore */ }

  function t(key) { var d = I18N[state.lang]; return (d && d[key]) || I18N.en[key] || key; }

  /* ---------------------------------------------------------------- DOM helpers (sem innerHTML) */
  function h(tag, props) {
    var node = document.createElement(tag);
    props = props || {};
    Object.keys(props).forEach(function (k) {
      var v = props[k];
      if (v === null || v === undefined || v === false) return;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k.slice(0, 2) === "on") node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v === true ? "" : v);
    });
    for (var i = 2; i < arguments.length; i++) append(node, arguments[i]);
    return node;
  }
  function append(node, child) {
    if (child === null || child === undefined || child === false) return;
    if (Array.isArray(child)) { child.forEach(function (c) { append(node, c); }); return; }
    node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); return node; }
  var app = document.getElementById("app");

  function fmtTime(iso) {
    if (!iso) return "";
    var d = new Date(iso); if (isNaN(d)) return "";
    var diff = (Date.now() - d.getTime()) / 60000;
    if (diff < 1) return t("now");
    return d.toLocaleString(state.lang === "pt" ? "pt-BR" : "en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }
  function channelLabel(c) { return c === "INSTAGRAM" ? t("instagram") : t("messenger"); }
  function legalLinks() {
    return h("div", { class: "legal" },
      h("a", { href: legal().privacy, target: "_blank", rel: "noopener", text: t("privacy") }),
      h("a", { href: legal().terms, target: "_blank", rel: "noopener", text: t("terms") }),
      h("a", { href: legal().deletion, target: "_blank", rel: "noopener", text: t("deletion") }));
  }
  function langSwitch(rerender) {
    function btn(code, label) { return h("button", { type: "button", class: state.lang === code ? "on" : "", onclick: function () { state.lang = code; try { localStorage.setItem("mdp_omni_lang", code); } catch (e) { /* ignore */ } document.documentElement.lang = code; rerender(); } , text: label }); }
    return h("div", { class: "lang" }, btn("en", "English"), " · ", btn("pt", "Português"));
  }

  /* ---------------------------------------------------------------- API */
  function parseDetail(data) { return data && typeof data.detail === "string" ? data.detail : ""; }

  async function doRefresh() {
    if (!state.refresh) return false;
    if (state.refreshing) return state.refreshing;
    state.refreshing = (async function () {
      try {
        var res = await fetch("/api/auth/refresh", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: state.refresh }) });
        var body = await res.json().catch(function () { return null; });
        if (!res.ok || !body || !body.access_token || !body.refresh_token) return false;
        state.access = body.access_token; state.refresh = body.refresh_token; return true;
      } catch (e) { return false; } finally { state.refreshing = null; }
    })();
    return state.refreshing;
  }

  async function api(path, opts) {
    opts = opts || {};
    var headers = { "Content-Type": "application/json" };
    if (state.access) headers.Authorization = "Bearer " + state.access;
    var res = await fetch(path, { method: opts.method || "GET", headers: headers, body: opts.body ? JSON.stringify(opts.body) : undefined });
    if (res.status === 401 && state.refresh && !opts.retried) {
      if (await doRefresh()) return api(path, Object.assign({}, opts, { retried: true }));
      signOut(t("session_expired"), true);
      throw new Error("session");
    }
    var data = null; try { data = await res.json(); } catch (e) { /* no body */ }
    if (!res.ok) { var err = new Error(parseDetail(data) || ("HTTP " + res.status)); err.status = res.status; err.data = data; throw err; }
    return data;
  }

  /* ---------------------------------------------------------------- sessao */
  function stopPoll() { if (state.poll) { clearInterval(state.poll); state.poll = null; } }
  function signOut(message, skipCall) {
    stopPoll();
    var rt = state.refresh, at = state.access;
    if (!skipCall && rt) { fetch("/api/auth/logout", { method: "POST", headers: { "Content-Type": "application/json", Authorization: "Bearer " + at }, body: JSON.stringify({ refresh_token: rt }) }).catch(function () { /* ignore */ }); }
    state.access = null; state.refresh = null; state.me = null; state.tab = null; state.inbox = { channel: null, selected: null }; state.comments = { channel: null };
    renderLogin(message ? { text: message, kind: "err" } : null);
  }

  function loginError(err) {
    if (err.status === 401) return t("err_credentials");
    if (err.status === 423) return t("err_locked");
    if (err.status === 403 && /expirad/i.test(err.message)) return t("err_expired");
    if (err.status === 403) return t("err_noaccess");
    if (err.status === 409) return t("err_mfa_setup");
    if (err.status === 422) return t("err_email");
    if (err.name === "TypeError") return t("err_network");
    return t("err_generic");
  }

  /* ---------------------------------------------------------------- login */
  function renderLogin(notice, pre) {
    stopPoll(); document.documentElement.lang = state.lang;
    var msg = h("div", { class: "notice err", role: "alert", style: notice ? "" : "display:none", text: notice ? notice.text : "" });
    var emailIn = h("input", { id: "email", type: "email", autocomplete: "username", placeholder: t("email_ph"), required: true, value: pre && pre.email ? pre.email : "" });
    var passIn = h("input", { id: "password", type: "password", autocomplete: "current-password", placeholder: t("password_ph"), required: true });
    var submit = h("button", { class: "btn primary", type: "submit", text: t("signin") });
    function show(text) { msg.style.display = text ? "" : "none"; msg.textContent = text || ""; }
    var form = h("form", { class: "card", novalidate: true, onsubmit: async function (ev) {
      ev.preventDefault(); show("");
      if (!emailIn.value.trim() || !passIn.value) { show(t("err_credentials")); return; }
      submit.disabled = true; submit.textContent = t("signing_in");
      try {
        var res = await fetch("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: emailIn.value.trim(), senha: passIn.value, contexto_plataforma: false }) });
        var body = await res.json().catch(function () { return null; });
        if (!res.ok) { var e = new Error(parseDetail(body)); e.status = res.status; throw e; }
        passIn.value = "";
        if (body.status === "AUTHENTICATED") { state.access = body.access_token; state.refresh = body.refresh_token; await enterApp(); return; }
        if (body.status === "MFA_VERIFY") { renderMfa(body.preauth_token); return; }
        show(t("err_mfa_setup"));
      } catch (err) { show(loginError(err)); }
      submit.disabled = false; submit.textContent = t("signin");
    } },
      h("div", { class: "field" }, h("h1", { text: t("signin") }), h("p", { text: t("signin_sub") })),
      msg,
      h("div", { class: "field" }, h("label", { for: "email", text: t("email") }), emailIn),
      h("div", { class: "field" }, h("label", { for: "password", text: t("password") }), passIn),
      submit);
    clear(app).appendChild(h("div", { class: "login" }, h("div", { class: "box" },
      h("div", { class: "top" }, h("div", { class: "brand" }, "MDP ", h("b", { text: "Omni" })), langSwitch(function () { renderLogin(null, { email: emailIn.value }); })),
      form, legalLinks())));
    emailIn.focus();
  }

  function renderMfa(preauth) {
    var msg = h("div", { class: "notice err", role: "alert", style: "display:none" });
    var code = h("input", { id: "code", type: "text", inputmode: "numeric", autocomplete: "one-time-code", maxlength: "6", pattern: "[0-9]{6}", required: true });
    var submit = h("button", { class: "btn primary", type: "submit", text: t("verify") });
    var form = h("form", { class: "card", novalidate: true, onsubmit: async function (ev) {
      ev.preventDefault(); msg.style.display = "none";
      submit.disabled = true;
      try {
        var res = await fetch("/api/auth/mfa/verify", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ preauth_token: preauth, codigo: code.value.trim() }) });
        var body = await res.json().catch(function () { return null; });
        if (!res.ok) { var e = new Error(parseDetail(body)); e.status = res.status; throw e; }
        state.access = body.access_token; state.refresh = body.refresh_token; await enterApp(); return;
      } catch (err) { msg.textContent = (err.status === 401 || err.status === 422) ? t("err_mfa_code") : loginError(err); msg.style.display = ""; }
      submit.disabled = false;
    } },
      h("div", { class: "field" }, h("h1", { text: t("mfa_title") }), h("p", { text: t("mfa_sub") })),
      msg, h("div", { class: "field" }, h("label", { for: "code", text: t("mfa_code") }), code),
      submit, h("button", { class: "btn", type: "button", text: t("back"), onclick: function () { renderLogin(); } }));
    clear(app).appendChild(h("div", { class: "login" }, h("div", { class: "box" },
      h("div", { class: "top" }, h("div", { class: "brand" }, "MDP ", h("b", { text: "Omni" })), langSwitch(function () { renderMfa(preauth); })), form, legalLinks())));
    code.focus();
  }

  /* ---------------------------------------------------------------- shell */
  function allowedTabs(perms) {
    var all = perms.indexOf("*") >= 0, tabs = [];
    if (all || perms.indexOf("OMNI_INTEGRACOES") >= 0) tabs.push("integrations");
    if (all || perms.indexOf("OMNI_INBOX") >= 0) tabs.push("inbox");
    if (all || perms.indexOf("OMNI_COMENTARIOS") >= 0) tabs.push("comments");
    return tabs;
  }

  async function enterApp() {
    try { state.me = await api("/api/auth/me"); } catch (e) { if (e.message !== "session") renderLogin({ text: t("err_generic"), kind: "err" }); return; }
    state.tabs = allowedTabs(state.me.permissoes || []);
    if (!state.tabs.length) { renderShell(h("main", {}, h("div", { class: "notice err", text: t("no_omni") }))); return; }
    var wanted = (location.hash || "").replace("#", "");
    state.tab = state.tabs.indexOf(wanted) >= 0 ? wanted : state.tabs[0];
    route();
  }

  function renderShell(content) {
    var tabLabels = { integrations: t("tab_integrations"), inbox: t("tab_inbox"), comments: t("tab_comments") };
    var nav = h("nav", { class: "tabs", "aria-label": "Main" }, (state.tabs || []).map(function (k) {
      return h("a", { href: "#" + k, class: state.tab === k ? "on" : "", "aria-current": state.tab === k ? "page" : null, onclick: function (ev) { ev.preventDefault(); location.hash = k; state.tab = k; route(); }, text: tabLabels[k] });
    }));
    var bar = h("header", { class: "bar" },
      h("div", { class: "l" }, h("div", { class: "brand" }, "MDP ", h("b", { text: "Omni" })), nav),
      h("div", { class: "r" },
        h("span", { class: "ws", text: t("workspace") + ": " + (state.me.tenant_nome || "") }),
        h("span", { text: state.me.nome || "" }),
        langSwitch(function () { route(); }),
        h("button", { class: "btn sm", type: "button", text: t("signout"), onclick: function () { signOut(); } })));
    clear(app).appendChild(h("div", {}, bar, content));
  }

  function route() {
    stopPoll();
    var holder = h("div");
    renderShell(holder);
    var view = state.tab === "inbox" ? viewInbox : state.tab === "comments" ? viewComments : viewIntegrations;
    view(holder);
  }

  /* ---------------------------------------------------------------- Integrations */
  function statusChip(status) {
    var cls = status === "CONNECTED" ? "ok" : (status === "EXPIRANDO" || status === "PENDENTE") ? "warn" : (status === "ERRO" || status === "EXPIRADO") ? "bad" : "";
    return h("span", { class: "chip " + cls, text: t("st_" + status) });
  }

  function viewIntegrations(root) {
    var notice = h("div", { class: "notice", role: "status", style: "display:none" });
    var grid = h("div", { class: "grid" }, h("div", { class: "empty", text: t("loading") }));
    root.appendChild(h("main", {}, h("div", {}, h("h1", { text: t("int_title") }), h("p", { class: "lead", text: t("int_lead") })), notice, grid,
      h("p", { class: "foot" }, t("int_foot") + " ", h("a", { href: legal().privacy, target: "_blank", rel: "noopener", text: t("privacy") }), " · ", h("a", { href: legal().deletion, target: "_blank", rel: "noopener", text: t("request_deletion") }))));
    function say(text, err) { notice.style.display = ""; notice.className = "notice" + (err ? " err" : ""); notice.textContent = text; }

    async function act(provider, method) {
      try { await api("/api/omni/integrations/" + provider + (method === "POST" ? "/connect" : ""), { method: method }); load(); }
      catch (e) { if (e.message === "session") return; say(e.status === 501 ? t(method === "POST" ? "not_enabled" : "disc_not_enabled") : t("err_generic"), true); }
    }
    function card(i) {
      var ig = i.provider === "INSTAGRAM", connected = i.status === "CONNECTED" || i.status === "EXPIRANDO";
      var name = i.account_name || "";
      return h("section", { class: "chan" },
        h("div", { class: "head" }, h("h2", { text: ig ? t("instagram") : t("facebook_page") }), statusChip(i.status)),
        connected ? h("div", { class: "acct" }, h("div", { class: "avatar", "aria-hidden": "true", text: (name[0] || "?").toUpperCase() }),
            h("div", {}, h("div", { style: "font-weight:600", text: name }), i.handle ? h("div", { class: "meta", text: "@" + i.handle }) : null))
          : h("p", { class: "lead", style: "font-size:15px", text: ig ? t("ig_desc") : t("fb_desc") }),
        h("div", { class: "meta" },
          connected ? [h("div", {}, h("b", { text: t("access_granted") + ": " }), ig ? t("ig_scopes") : t("fb_scopes")), h("div", {}, h("b", { text: t("connection") + ": " }), t("renews"))]
            : [h("div", {}, h("b", { text: t("you_choose") + ": " }), t("you_choose_v")), h("div", {}, h("b", { text: t("control") + ": " }), t("control_v"))]),
        h("div", { class: "acts" }, connected
          ? [h("button", { class: "btn", type: "button", text: t("reconnect"), onclick: function () { act(i.provider, "POST"); } }), h("button", { class: "btn danger", type: "button", text: t("disconnect"), onclick: function () { act(i.provider, "DELETE"); } })]
          : h("button", { class: "btn primary", type: "button", text: ig ? t("connect_ig") : t("connect_fb"), onclick: function () { act(i.provider, "POST"); } })));
    }
    async function load() {
      try { var list = await api("/api/omni/integrations"); clear(grid); list.forEach(function (i) { grid.appendChild(card(i)); }); }
      catch (e) { if (e.message !== "session") { clear(grid); say(t("err_generic"), true); } }
    }
    load();
  }

  /* ---------------------------------------------------------------- Inbox */
  function filterBar(current, onPick) {
    function b(code, label) { return h("button", { type: "button", class: current === code ? "on" : "", onclick: function () { onPick(code); }, text: label }); }
    return h("div", { class: "filters" }, b(null, t("all")), b("INSTAGRAM", t("instagram")), b("FACEBOOK", t("messenger")));
  }
  function errText(code) { return code === "channel_not_connected" ? t("not_sent") : t("not_sent_gen"); }

  function viewInbox(root) {
    var list = h("div", {}, h("div", { class: "empty", text: t("loading") }));
    var pane = h("section", { class: "thread" }, h("div", { class: "empty", text: t("pick_conv") }));
    var aside = h("aside", {}, h("div", { class: "hd" }, h("h1", { text: t("inbox") }), h("div", { id: "filters" })), list);
    root.appendChild(h("div", { class: "inbox" }, aside, pane));

    function drawFilters() { var f = aside.querySelector("#filters"); clear(f).appendChild(filterBar(state.inbox.channel, function (c) { state.inbox.channel = c; state.inbox.selected = null; drawPaneEmpty(); loadList(); })); }
    function drawPaneEmpty() { clear(pane).appendChild(h("div", { class: "empty", text: t("pick_conv") })); }

    function drawList(items) {
      clear(list);
      if (!items.length) { list.appendChild(h("div", { class: "empty", text: t("no_convs") })); return; }
      items.forEach(function (c) {
        list.appendChild(h("button", { type: "button", class: "conv" + (state.inbox.selected === c.id ? " on" : ""), onclick: function () { open(c.id); } },
          h("div", { class: "row" }, h("div", { class: "nm" }, h("span", { text: c.name || c.username || "—" }), h("span", { class: "tag " + c.channel, text: channelLabel(c.channel) }), c.unread > 0 ? h("span", { class: "dot", title: String(c.unread), "aria-label": c.unread + " unread" }) : null), h("span", { class: "tm", text: fmtTime(c.last_message_at) })),
          h("div", { class: "tx", text: c.last_text || "" })));
      });
    }

    async function loadList() {
      try { var q = state.inbox.channel ? "?channel=" + state.inbox.channel : ""; drawList(await api("/api/omni/conversations" + q)); }
      catch (e) { if (e.message !== "session") { clear(list).appendChild(h("div", { class: "empty", text: t("err_generic") })); } }
    }

    var shownIds = {};
    function drawThread(data) {
      shownIds = {}; data.messages.forEach(function (m) { shownIds[m.id] = true; });
      var c = data.conversation, closed = !c.reply_window_open;
      var msgs = h("div", { class: "msgs", id: "msgs" }, data.messages.map(msgNode));
      var input = h("input", { type: "text", maxlength: "1000", placeholder: closed ? t("closed_note") : t("reply_ph"), disabled: closed, "aria-label": t("reply_ph") });
      var send = h("button", { class: "btn primary", type: "submit", disabled: closed, text: t("send") });
      var info = h("div", { class: "info bad", style: "padding:0 28px 14px", role: "status" });
      var form = h("form", { class: "composer", onsubmit: async function (ev) {
        ev.preventDefault(); var text = input.value.trim(); info.textContent = "";
        if (!text) { info.textContent = t("err_empty"); return; }
        send.disabled = true; send.textContent = t("sending");
        try {
          var m = await api("/api/omni/conversations/" + c.id + "/reply", { method: "POST", body: { text: text } });
          shownIds[m.id] = true; msgs.appendChild(msgNode(m)); msgs.scrollTop = msgs.scrollHeight; input.value = "";
          if (m.status !== "ENVIADA") info.textContent = t("saved_not_sent");
          loadList();
        } catch (e) { if (e.message !== "session") info.textContent = e.status === 409 ? t("err_window") : e.status === 422 ? t("err_empty") : t("err_generic"); }
        send.disabled = false; send.textContent = t("send");
      } }, input, send);
      clear(pane).appendChild(h("div", { style: "display:flex;flex-direction:column;flex:1;min-height:0" },
        h("div", { class: "th" }, h("div", { class: "who" }, h("div", { class: "avatar", "aria-hidden": "true", text: ((c.name || c.username || "?")[0] || "?").toUpperCase() }),
          h("div", {}, h("div", { class: "n", text: c.name || c.username || "—" }), h("div", { class: "s", text: c.channel === "INSTAGRAM" ? t("via_ig") : t("via_fb") }))),
          h("span", { class: "chip " + (closed ? "" : "ok"), text: closed ? t("window_closed") : t("window_open") })),
        msgs, info, form));
      msgs.scrollTop = msgs.scrollHeight;
    }
    function msgNode(m) {
      var out = m.direction === "SAIDA";
      var meta = out ? (m.status === "ENVIADA" ? t("sent_ok") : errText(m.error)) : "";
      return h("div", { class: "m " + (out ? "out" : "in") }, h("div", { class: "bub", text: m.text || "" }),
        h("div", { class: "info" + (out && m.status !== "ENVIADA" ? " bad" : ""), text: (meta ? meta + " · " : "") + fmtTime(m.at) }));
    }

    async function open(id) {
      state.inbox.selected = id;
      try { drawThread(await api("/api/omni/conversations/" + id + "/messages")); loadList(); }
      catch (e) { if (e.message !== "session") clear(pane).appendChild(h("div", { class: "empty", text: t("err_generic") })); }
    }

    async function refreshOpen() {
      var id = state.inbox.selected, box = pane.querySelector("#msgs");
      if (!id || !box) return;
      try {
        var data = await api("/api/omni/conversations/" + id + "/messages");
        if (state.inbox.selected !== id) return;
        var fresh = data.messages.filter(function (m) { return !shownIds[m.id]; });
        fresh.forEach(function (m) { shownIds[m.id] = true; box.appendChild(msgNode(m)); });
        if (fresh.length) box.scrollTop = box.scrollHeight;
      } catch (e) { /* tenta de novo no proximo ciclo */ }
    }

    drawFilters(); loadList();
    state.poll = setInterval(function () { loadList(); refreshOpen(); }, POLL_MS);
  }

  /* ---------------------------------------------------------------- Comments */
  function viewComments(root) {
    var listBox = h("div", { style: "display:flex;flex-direction:column;gap:18px" }, h("div", { class: "empty", text: t("loading") }));
    var filters = h("div");
    root.appendChild(h("main", { style: "max-width:1040px" }, h("div", { style: "display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap" }, h("h1", { text: t("comments") }), filters), listBox));
    function drawFilters() { clear(filters).appendChild(filterBar(state.comments.channel, function (c) { state.comments.channel = c; load(); drawFilters(); })); }

    function replyNode(r) {
      var ok = r.status === "ENVIADA";
      return h("div", { class: "rp" }, h("div", { class: "by" + (ok ? "" : " bad"), text: (ok ? t("sent_by") : errText(r.error)) + " · " + fmtTime(r.at) }), h("div", { class: "t", text: r.text || "" }));
    }
    function card(c) {
      var replies = h("div", { style: "display:flex;flex-direction:column;gap:10px" }, c.replies.map(replyNode));
      var who = c.author_username ? "@" + c.author_username : (c.author_name || "—");
      var composerBox = h("div");
      var open = h("button", { class: "btn sm", type: "button", text: t("reply"), onclick: function () {
        var input = h("input", { type: "text", maxlength: "1000", placeholder: t("reply_to") + who + "…", "aria-label": t("reply_to") + who });
        var send = h("button", { class: "btn primary", type: "submit", text: t("reply") });
        var info = h("div", { class: "info bad", style: "font-size:13px;color:#f5c26b;margin-top:8px", role: "status" });
        clear(composerBox).appendChild(h("div", {}, h("form", { class: "composer", onsubmit: async function (ev) {
          ev.preventDefault(); var text = input.value.trim(); info.textContent = ""; if (!text) { info.textContent = t("err_empty"); return; }
          send.disabled = true; send.textContent = t("sending");
          try { var r = await api("/api/omni/comments/" + c.id + "/reply", { method: "POST", body: { text: text } }); replies.appendChild(replyNode(r)); input.value = ""; if (r.status !== "ENVIADA") info.textContent = t("saved_not_sent"); }
          catch (e) { if (e.message !== "session") info.textContent = e.status === 422 ? t("err_empty") : t("err_generic"); }
          send.disabled = false; send.textContent = t("reply");
        } }, input, send), info));
        input.focus(); open.style.display = "none";
      } });
      return h("article", { class: "cm" },
        h("div", { class: "src" }, h("div", { style: "display:flex;gap:10px;align-items:center;flex-wrap:wrap" }, h("span", { class: "tag " + c.channel, text: channelLabel(c.channel) }), c.post ? h("span", { text: t("on_post") + ": \u201C" + c.post + "\u201D" }) : null), c.replied ? h("span", { class: "chip ok", text: t("replied") }) : null),
        h("div", {}, h("div", { class: "au" }, h("b", { text: c.author_name || who }), h("span", { text: fmtTime(c.at) })), h("div", { class: "tx", text: c.text || "" })),
        replies, composerBox, open);
    }
    async function load() {
      try {
        var q = state.comments.channel ? "?channel=" + state.comments.channel : "";
        var items = await api("/api/omni/comments" + q); clear(listBox);
        if (!items.length) listBox.appendChild(h("div", { class: "empty", text: t("no_comments") }));
        items.forEach(function (c) { listBox.appendChild(card(c)); });
      } catch (e) { if (e.message !== "session") clear(listBox).appendChild(h("div", { class: "empty", text: t("err_generic") })); }
    }
    drawFilters(); load();
  }

  /* ---------------------------------------------------------------- start */
  document.documentElement.lang = state.lang;
  renderLogin();
})();
