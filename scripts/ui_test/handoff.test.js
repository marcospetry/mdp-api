// Testa a passagem de sessao do backoffice (/login) para o /omni, contra a API REAL, em um navegador simulado.
const { JSDOM, VirtualConsole } = require("jsdom");
const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const SENHA = "SenhaE2E#12345";
const results = [];
const ok = (n, c, d) => { results.push(!!c); console.log((c ? "  OK   " : "  FALHA") + "  " + n + (c || !d ? "" : "  [" + d + "]")); };
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
async function until(fn, ms = 6000) { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (fn()) return true; } catch (e) {} await sleep(60); } return false; }

async function open(path, beforeParse) {
  const vc = new VirtualConsole(); vc.on("jsdomError", () => {}); // jsdom nao implementa navegacao: ignora
  const dom = await JSDOM.fromURL(BASE + path, { runScripts: "dangerously", resources: "usable", pretendToBeVisual: true, virtualConsole: vc,
    beforeParse(w) { w.fetch = (u, o) => fetch(new URL(u, BASE), o); if (beforeParse) beforeParse(w); } });
  await until(() => dom.window.document.readyState === "complete"); await sleep(300);
  return dom.window;
}
async function apiLogin(email) {
  const r = await fetch(BASE + "/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, senha: SENHA, contexto_plataforma: false }) });
  return r.json();
}
async function loginViaSpa(email) {
  const w = await open("/login"); const d = w.document;
  d.getElementById("email").value = email; d.getElementById("senha").value = SENHA;
  d.getElementById("loginForm").dispatchEvent(new w.Event("submit", { bubbles: true, cancelable: true }));
  return w;
}

(async () => {
  console.log("\n[1] Login pelo backoffice (/login) com usuario SO-OMNI");
  let w = await loginViaSpa("e2e.revisor@exemplo-teste.com.br");
  const got = await until(() => w.sessionStorage.getItem("mdp_omni_handoff"));
  const h = got ? JSON.parse(w.sessionStorage.getItem("mdp_omni_handoff")) : null;
  ok("1.1 a sessao e entregue para o /omni (redirecionamento disparado)", h && h.a && h.r && typeof h.t === "number");
  ok("1.2 o backoffice NAO chega a mostrar o painel para o revisor", !/Olá,/.test(w.document.getElementById("welcomeName").textContent));

  console.log("\n[2] Login pelo backoffice com usuario ADMIN (acesso total) NAO e redirecionado");
  w = await loginViaSpa("e2e.admin@exemplo-teste.com.br");
  ok("2.1 o painel do backoffice abre normalmente", await until(() => /Olá, E2E Admin/.test(w.document.getElementById("welcomeName").textContent)));
  ok("2.2 nenhuma sessao e entregue ao /omni", !w.sessionStorage.getItem("mdp_omni_handoff"));

  console.log("\n[3] /omni aceita a sessao entregue");
  const s = await apiLogin("e2e.revisor@exemplo-teste.com.br");
  w = await open("/omni", (win) => win.sessionStorage.setItem("mdp_omni_handoff", JSON.stringify({ a: s.access_token, r: s.refresh_token, t: Date.now() })));
  ok("3.1 entra direto, sem tela de login, com as abas do Omni", await until(() => w.document.querySelector("nav.tabs") && !w.document.getElementById("email")));
  ok("3.2 workspace 'MDP Demo' no topo", /Workspace: MDP Demo/.test(w.document.body.textContent));
  ok("3.3 a sessao entregue e APAGADA ao ser lida (uso unico)", !w.sessionStorage.getItem("mdp_omni_handoff"));

  console.log("\n[4] Entregas invalidas caem no login normal");
  const s2 = await apiLogin("e2e.revisor@exemplo-teste.com.br");
  w = await open("/omni", (win) => win.sessionStorage.setItem("mdp_omni_handoff", JSON.stringify({ a: s2.access_token, r: s2.refresh_token, t: Date.now() - 60000 })));
  ok("4.1 entrega com mais de 30 s e ignorada e apagada", await until(() => w.document.getElementById("email")) && !w.sessionStorage.getItem("mdp_omni_handoff"));
  w = await open("/omni", (win) => win.sessionStorage.setItem("mdp_omni_handoff", "isto-nao-e-json"));
  ok("4.2 entrega corrompida e ignorada e apagada", await until(() => w.document.getElementById("email")) && !w.sessionStorage.getItem("mdp_omni_handoff"));
  w = await open("/omni");
  ok("4.3 sem entrega, o /omni mostra o login em ingles", await until(() => w.document.getElementById("email")) && /Sign in/.test(w.document.body.textContent));

  const f = results.filter(x => !x).length;
  console.log(`\nResumo: ${results.length - f} ok, ${f} falha(s) de ${results.length} verificacoes.`);
  process.exit(f ? 1 : 0);
})().catch(e => { console.error("ERRO NO TESTE:", e); process.exit(2); });
