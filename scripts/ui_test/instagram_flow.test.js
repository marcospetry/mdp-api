// Testa as telas do Instagram (conectar, voltar do Instagram, status, comentarios, erros de envio) em navegador simulado, contra a API REAL.
// A Meta nunca e chamada: as respostas especificas sao simuladas por interceptacao do fetch.
const { JSDOM, VirtualConsole } = require("jsdom");
const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const SENHA = "SenhaE2E#12345";
const results = [];
const ok = (n, c, d) => { results.push(!!c); console.log((c ? "  OK   " : "  FALHA") + "  " + n + (c || !d ? "" : "  [" + d + "]")); };
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
async function until(fn, ms = 6000) { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (fn()) return true; } catch (e) {} await sleep(60); } return false; }
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

async function open(path, { before, intercept } = {}) {
  const vc = new VirtualConsole(); vc.on("jsdomError", () => {});
  const calls = [];
  const dom = await JSDOM.fromURL(BASE + path, { runScripts: "dangerously", resources: "usable", pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) {
      w.fetch = async (u, o) => { const url = new URL(u, BASE); calls.push({ method: (o && o.method) || "GET", path: url.pathname }); const hit = intercept && await intercept(url.pathname, o); return hit || fetch(url, o); };
      w.confirm = () => true;
      if (before) before(w);
    } });
  await until(() => dom.window.document.readyState === "complete"); await sleep(300);
  dom.window.__calls = calls; return dom.window;
}
async function apiLogin(email) {
  const r = await fetch(BASE + "/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, senha: SENHA, contexto_plataforma: false }) });
  return r.json();
}
const stashReturn = (refresh, age = 0) => (w) => w.sessionStorage.setItem("mdp_omni_return", JSON.stringify({ r: refresh, t: Date.now() - age }));
const text = (w, sel) => (sel ? w.document.querySelector(sel) : w.document.body).textContent.replace(/\s+/g, " ");
const click = (w, el) => el.dispatchEvent(new w.MouseEvent("click", { bubbles: true, cancelable: true }));
const btn = (w, label) => [...w.document.querySelectorAll("button")].find(b => b.textContent === label);
const integ = (status, extra = {}) => json([{ provider: "INSTAGRAM", status, account_name: "MDP Demo", handle: "mdpdemo", connected_at: null, token_expires_at: null, ...extra },
                                            { provider: "FACEBOOK", status: "NOT_CONNECTED", account_name: null, handle: null, connected_at: null, token_expires_at: null }]);

(async () => {
  const s = await apiLogin("e2e.revisor@exemplo-teste.com.br");
  let w;

  console.log("\n[1] Conectar: o botao leva ao Instagram e guarda a sessao para a volta");
  w = await open("/omni", { before: (win) => win.sessionStorage.setItem("mdp_omni_handoff", JSON.stringify({ a: s.access_token, r: s.refresh_token, t: Date.now() })),
    intercept: async (p, o) => { if (p === "/api/omni/integrations/INSTAGRAM/connect") return json({ authorization_url: "https://www.instagram.com/oauth/authorize?client_id=1&state=x" }); } });
  await until(() => w.document.querySelector(".chan"));
  click(w, btn(w, "Connect Instagram"));
  const stash = await until(() => w.sessionStorage.getItem("mdp_omni_return"));
  const st = stash ? JSON.parse(w.sessionStorage.getItem("mdp_omni_return")) : null;
  ok("1.1 clicar em Connect pede a URL de autorizacao ao servidor", w.__calls.some(c => c.method === "POST" && c.path === "/api/omni/integrations/INSTAGRAM/connect"));
  ok("1.2 antes de sair, guarda o refresh token para recuperar a sessao na volta", st && st.r && typeof st.t === "number");

  console.log("\n[2] Volta do Instagram");
  const fresh = await apiLogin("e2e.revisor@exemplo-teste.com.br");
  w = await open("/omni?ig=connected", { before: stashReturn(fresh.refresh_token), intercept: async (p) => { if (p === "/api/omni/integrations") return integ("CONNECTED"); } });
  ok("2.1 recupera a sessao sozinho (sem pedir login) e abre em Integrations", await until(() => w.document.querySelector("nav.tabs a.on") && /Integrations/.test(text(w, "nav.tabs a.on"))));
  ok("2.2 mostra 'Instagram connected.' e limpa a URL", await until(() => /Instagram connected\./.test(text(w))) && !w.location.search);
  ok("2.3 o cartao do Instagram aparece como Connected, com o @usuario", await until(() => /Connected/.test(text(w, ".chan .chip")) && /@mdpdemo/.test(text(w))));
  ok("2.4 a sessao guardada e de USO UNICO (apagada ao ler)", !w.sessionStorage.getItem("mdp_omni_return"));
  const cases = { already_connected: /already connected to another workspace/, denied: /cancelled/, state: /expired or could not be verified/, not_professional: /professional account/, permissions: /allow all requested permissions/, exchange: /did not accept/, disabled: /not enabled yet/, inventado: /Something went wrong/ };
  let all = true;
  for (const [code, re] of Object.entries(cases)) {
    const f = await apiLogin("e2e.revisor@exemplo-teste.com.br");
    w = await open("/omni?ig_error=" + code, { before: stashReturn(f.refresh_token) });
    if (!(await until(() => re.test(text(w, ".notice.err"))))) { all = false; console.log("      sem mensagem esperada para", code); }
  }
  ok("2.5 cada erro da volta mostra uma mensagem clara em ingles (e codigo desconhecido cai numa mensagem generica)", all);
  w = await open("/omni?ig=connected&ig_warn=webhook", { before: stashReturn((await apiLogin("e2e.revisor@exemplo-teste.com.br")).refresh_token) });
  ok("2.6 conectado sem confirmar os webhooks mostra o aviso e a dica de Refresh", await until(() => /real-time updates could not be confirmed/.test(text(w))));
  w = await open("/omni?ig=connected", { before: stashReturn((await apiLogin("e2e.revisor@exemplo-teste.com.br")).refresh_token, 20 * 60000) });
  ok("2.7 sessao guardada ha mais de 15 min e ignorada: cai no login com o aviso", await until(() => w.document.getElementById("email")) && /Instagram connected/.test(text(w)));
  w = await open("/omni?ig=connected", { before: stashReturn("token-invalido") });
  ok("2.8 refresh token invalido: cai no login, sem erro de tela", await until(() => w.document.getElementById("email")));

  console.log("\n[3] Estados do canal");
  const f3 = await apiLogin("e2e.revisor@exemplo-teste.com.br");
  for (const [status, chip, button] of [["NOT_CONNECTED", "Not connected", "Connect Instagram"], ["CONNECTED", "Connected", "Reconnect"], ["EXPIRING", "Expiring soon", "Reconnect"],
                                        ["EXPIRED", "Expired", "Reconnect"], ["ERROR", "Error", "Reconnect"], ["REVOKED", "Disconnected", "Connect Instagram"], ["PENDING", "Pending", "Connect Instagram"]]) {
    w = await open("/omni", { before: (win) => win.sessionStorage.setItem("mdp_omni_handoff", JSON.stringify({ a: f3.access_token, r: f3.refresh_token, t: Date.now() })), intercept: async (p) => { if (p === "/api/omni/integrations") return integ(status); } });
    await until(() => w.document.querySelector(".chan .chip"));
    ok(`3.x ${status}: chip '${chip}' e botao '${button}'`, text(w, ".chan .chip") === chip && !!btn(w, button));
  }
  w = await open("/omni", { before: (win) => win.sessionStorage.setItem("mdp_omni_handoff", JSON.stringify({ a: f3.access_token, r: f3.refresh_token, t: Date.now() })), intercept: async (p, o) => {
    if (p === "/api/omni/integrations" ) return integ("CONNECTED"); if (p === "/api/omni/integrations/INSTAGRAM" && o && o.method === "DELETE") return json({ disconnected: true }); } });
  await until(() => btn(w, "Disconnect"));
  click(w, btn(w, "Disconnect"));
  ok("3.8 Disconnect pede confirmacao, chama a API e avisa", await until(() => w.__calls.some(c => c.method === "DELETE" && c.path === "/api/omni/integrations/INSTAGRAM") && /Account disconnected/.test(text(w))));

  console.log("\n[4] Comentarios: sincroniza ao abrir e tem botao Atualizar");
  const f4 = await apiLogin("e2e.revisor@exemplo-teste.com.br");
  w = await open("/omni#comments", { before: (win) => win.sessionStorage.setItem("mdp_omni_handoff", JSON.stringify({ a: f4.access_token, r: f4.refresh_token, t: Date.now() })) });
  await until(() => btn(w, "Refresh"));
  const syncs = () => w.__calls.filter(c => c.method === "POST" && c.path === "/api/omni/comments/sync").length;
  ok("4.1 ao abrir, consulta o Instagram por comentarios novos", await until(() => syncs() >= 1));
  const antes = syncs(); click(w, btn(w, "Refresh"));
  ok("4.2 o botao Refresh sincroniza de novo, recarrega a lista e volta ao normal", await until(() => syncs() === antes + 1) && await until(() => btn(w, "Refresh") && !btn(w, "Refresh").disabled));
  w = await open("/omni#comments", { before: (win) => win.sessionStorage.setItem("mdp_omni_handoff", JSON.stringify({ a: f4.access_token, r: f4.refresh_token, t: Date.now() })), intercept: async (p) => { if (p === "/api/omni/comments/sync") return json({ detail: "x" }, 500); } });
  ok("4.3 erro na sincronizacao nao derruba a tela (a lista segue aparecendo)", await until(() => w.document.querySelector("h1") && /Comments/.test(text(w, "h1"))) && !/Something went wrong/.test(text(w)));

  console.log("\n[5] Mensagens de erro no envio");
  const f5 = await apiLogin("e2e.revisor@exemplo-teste.com.br");
  for (const [code, re] of [["meta_190", /connection expired. Reconnect/], ["meta_unavailable", /Instagram is unavailable/], ["meta_100", /Instagram rejected/], ["channel_not_connected", /channel not connected/]]) {
    w = await open("/omni#inbox", { before: (win) => win.sessionStorage.setItem("mdp_omni_handoff", JSON.stringify({ a: f5.access_token, r: f5.refresh_token, t: Date.now() })), intercept: async (p, o) => {
      if (/\/reply$/.test(p) && o && o.method === "POST") return json({ id: "1", direction: "SAIDA", text: "oi", status: "FALHA", error: code, at: new Date().toISOString() }, 201); } });
    await until(() => w.document.querySelectorAll(".conv").length);
    click(w, [...w.document.querySelectorAll(".conv")].find(c => /Maria S\./.test(c.textContent)) || w.document.querySelector(".conv"));
    await until(() => w.document.querySelector(".composer input") && !w.document.querySelector(".composer input").disabled);
    const input = w.document.querySelector(".composer input"); input.value = "oi"; w.document.querySelector(".composer").dispatchEvent(new w.Event("submit", { bubbles: true, cancelable: true }));
    ok(`5.x erro '${code}' vira uma mensagem clara`, await until(() => re.test(text(w, ".msgs"))));
  }

  const f = results.filter(x => !x).length;
  console.log(`\nResumo: ${results.length - f} ok, ${f} falha(s) de ${results.length} verificacoes.`);
  process.exit(f ? 1 : 0);
})().catch(e => { console.error("ERRO NO TESTE:", e); process.exit(2); });
