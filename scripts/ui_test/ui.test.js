const { JSDOM } = require("jsdom");
const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
const results = [];
const ok = (name, cond, detail) => { results.push(!!cond); console.log((cond ? "  OK   " : "  FALHA") + "  " + name + (cond || !detail ? "" : "  [" + detail + "]")); };
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
  const dom = await JSDOM.fromURL(BASE + "/omni", {
    runScripts: "dangerously", resources: "usable", pretendToBeVisual: true,
    beforeParse(window) { window.fetch = (u, o) => fetch(new URL(u, BASE), o); }
  });
  const w = dom.window, d = w.document;
  const $ = (s, r) => (r || d).querySelector(s), $$ = (s, r) => [...(r || d).querySelectorAll(s)];
  const text = (r) => (r || d.body).textContent.replace(/\s+/g, " ");
  async function until(fn, label, ms = 6000) { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (fn()) return true; } catch (e) {} await sleep(60); } return false; }
  const click = (el) => el.dispatchEvent(new w.MouseEvent("click", { bubbles: true, cancelable: true }));
  const submit = (form) => form.dispatchEvent(new w.Event("submit", { bubbles: true, cancelable: true }));
  const type = (el, v) => { el.value = v; el.dispatchEvent(new w.Event("input", { bubbles: true })); };

  console.log("\n[1] Login (ingles, sem checkbox)");
  await until(() => $("#email"), "login");
  ok("1.1 tela de login em ingles", /Sign in/.test(text()) && /Privacy Policy/.test(text()) && /Data deletion/.test(text()));
  ok("1.2 sem checkbox de Plataforma", $$("input[type=checkbox]").length === 0);
  ok("1.3 links legais do login (EN) apontam para as paginas em ingles", $$("a").some(a => a.href.endsWith("/privacy-policy-en.html#data-deletion")) && $$("a").some(a => a.href.endsWith("/terms-of-service-en.html")) && $$("a").some(a => a.href.endsWith("/privacy-policy-en.html")));
  type($("#email"), "e2e.revisor@exemplo-teste.com.br"); type($("#password"), "senha-errada"); submit($("form"));
  ok("1.4 senha errada mostra erro em ingles", await until(() => /Invalid email or password/.test(text()), "err"));
  type($("#password"), "SenhaE2E#12345"); submit($("form"));
  ok("1.5 login do revisor entra direto (sem MFA)", await until(() => $("nav.tabs"), "app"));

  console.log("\n[2] Shell e permissoes");
  ok("2.1 workspace 'MDP Demo' e usuario no topo", /Workspace: MDP Demo/.test(text()) && /E2E Revisor/.test(text()));
  const tabs = $$("nav.tabs a").map(a => a.textContent);
  ok("2.2 abas: Integrations, Inbox, Comments", JSON.stringify(tabs) === JSON.stringify(["Integrations", "Inbox", "Comments"]), JSON.stringify(tabs));
  ok("2.3 nenhum item do backoffice no menu", !/Empresas|Contatos|Diagn|Plataforma/.test(text()));

  console.log("\n[3] Integrations");
  ok("3.1 dois cartoes: Instagram e Facebook Page, ambos 'Not connected'", await until(() => $$(".chan").length === 2 && $$(".chan .chip").every(c => c.textContent === "Not connected"), "cards"));
  ok("3.2 botoes Connect Instagram / Connect Facebook Page", /Connect Instagram/.test(text()) && /Connect Facebook Page/.test(text()));
  click($$("button").find(b => b.textContent === "Connect Instagram"));
  ok("3.3 Connect avisa que ainda nao esta habilitado", await until(() => /Connecting channels is not enabled yet/.test(text()), "501"));
  ok("3.4 rodape de Integrations (EN): politica e exclusao de dados em ingles", $$(".foot a").some(a => a.href.endsWith("/privacy-policy-en.html")) && $$(".foot a").some(a => a.href.endsWith("/privacy-policy-en.html#data-deletion")));

  console.log("\n[4] Inbox");
  click($$("nav.tabs a").find(a => a.textContent === "Inbox"));
  ok("4.1 lista com 3 conversas e selos de canal", await until(() => $$(".conv").length === 3, "convs") && $$(".conv .tag.INSTAGRAM").length === 2 && $$(".conv .tag.FACEBOOK").length === 1);
  ok("4.2 conversa com nao lida tem o marcador", $$(".conv .dot").length === 1);
  click($$(".conv").find(c => /Maria S\./.test(c.textContent)));
  ok("4.3 abre a conversa com 3 mensagens e janela de 24h aberta", await until(() => $$(".msgs .m").length === 3, "thread") && /24-hour reply window open/.test(text()));
  const input = $(".composer input"); type(input, "See you Thursday at 10!"); submit($(".composer"));
  ok("4.4 resposta aparece como NAO enviada (canal nao conectado)", await until(() => $$(".msgs .m.out").length === 2 && /Not sent: channel not connected/.test(text($(".msgs"))), "reply"));
  ok("4.5 aviso 'Saved, but not sent'", /Saved, but not sent/.test(text()));
  click($$(".conv").find(c => /Ana C\./.test(c.textContent)));
  ok("4.6 janela fechada desabilita a resposta", await until(() => /24-hour reply window closed/.test(text()) && $(".composer input").disabled && $(".composer button").disabled, "closed"));
  ok("4.7 SEGURANCA: HTML de terceiros aparece como texto, sem virar elemento", $$(".msgs img").length === 0 && /<img src=x/.test(text($(".msgs"))) && !w.__xss);
  click($$(".filters button").find(b => b.textContent === "Messenger"));
  ok("4.8 filtro Messenger mostra so a conversa do Facebook", await until(() => $$(".conv").length === 1 && /João P\./.test(text($(".conv"))), "filter"));

  console.log("\n[5] Comments");
  click($$("nav.tabs a").find(a => a.textContent === "Comments"));
  ok("5.1 lista 3 comentarios com post de origem", await until(() => $$(".cm").length === 3, "comments") && /On post: .Spring promotion, book this week./.test(text()));
  ok("5.2 comentario ja respondido mostra a resposta e o selo", /Replied/.test(text()) && /Thank you, Pedro/.test(text()));
  const carla = $$(".cm").find(c => /Carla M\./.test(c.textContent));
  click($$("button", carla).find(b => b.textContent === "Reply"));
  ok("5.3 caixa de resposta abre", await until(() => $("form.composer", carla), "box"));
  type($("form.composer input", carla), "Yes, weekends too."); submit($("form.composer", carla));
  ok("5.4 resposta aparece sob o comentario como NAO enviada", await until(() => /Not sent: channel not connected/.test(text(carla)) && /Yes, weekends too/.test(text(carla)), "creply"));

  console.log("\n[6] Idioma e sessao");
  click($$("nav.tabs a").find(a => a.textContent === "Integrations"));
  await until(() => $$(".chan").length === 2, "int");
  click($$(".lang button").find(b => b.textContent === "Português"));
  ok("6.1 alternar para Portugues traduz a tela", await until(() => /Comentários/.test(text($("nav.tabs"))) && /Sair/.test(text()), "pt"));
  ok("6.1b links legais passam a apontar para as paginas em portugues", $$(".foot a").some(a => a.href.endsWith("/politica-de-privacidade.html")) && $$(".foot a").some(a => a.href.endsWith("/politica-de-privacidade.html#exclusao-de-dados")));
  click($$(".lang button").find(b => b.textContent === "English"));
  click($$("button").find(b => /Sign out/.test(b.textContent)));
  ok("6.2 Sign out volta ao login", await until(() => $("#email") && !$("nav.tabs"), "logout"));

  const fails = results.filter(x => !x).length;
  console.log(`\nResumo: ${results.length - fails} ok, ${fails} falha(s) de ${results.length} verificacoes.`);
  process.exit(fails ? 1 : 0);
})().catch(e => { console.error("ERRO NO TESTE:", e); process.exit(2); });
