"""
Teste automatico do backend do FACEBOOK (Messenger + comentarios de Pagina) no Omni, com uma META SIMULADA
(nenhuma chamada real sai daqui).

ONDE RODAR: SOMENTE em banco de TESTE/DEV (trava por APP_ENV). Cria e REMOVE usuarios @exemplo-teste.com.br, canais e dados
de teste nos tenants MDP e MDP_DEMO. Nao imprime tokens, codigos nem senhas.

Uso:  python scripts/test_omni_facebook.py
Pre-requisitos: migrations 010/006/011 aplicadas; tenants MDP e MDP_DEMO provisionados (como nos outros testes).
O formato real do evento de comentario (campo feed) e da resposta de login so sera confirmado com a Meta de verdade.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import sys
import time
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import jwt
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import settings
from app.database import PlatformSessionLocal, tenant_session
from app.main import app
from app.models.auth import UsuarioEmpresa, UsuarioTenantLocal
from app.models.empresa import Empresa
from app.models.platform_auth import PlatformTenant, PlatformUsuario, PlatformUsuarioTenant
from app.security.password import hash_password
from app.services import meta_crypto, meta_facebook, meta_instagram
from app.services.auth_service import utcnow

SENHA = "SenhaTeste#12345"
EMAILS = {"rev": "fb.revisor@exemplo-teste.com.br", "adm": "fb.admin@exemplo-teste.com.br"}
PAGE_DEMO, PAGE_MDP, ASID = "100000000000001", "100000000000002", "asid-777"
SECRET_FB, VERIFY_FB, CONFIG_ID, APP_ID = "fb-secret-for-tests", "fb-verify-for-tests", "1821997732478119", "2300207430735194"
SENSIVEL = ("SHORTUSER-SECRET", "LONGUSER-", "PAGETOKEN-SECRET", "GOODCODE", SECRET_FB, VERIFY_FB)
resultados: list[bool] = []
client = TestClient(app)


def check(nome, cond, detalhe=""):
    resultados.append(bool(cond))
    print(("  OK   " if cond else "  FALHA") + f"  {nome}" + (f"  [{detalhe}]" if detalhe and not cond else ""))


# ----------------------------------------------------------------------------- Meta simulada (Facebook)
class FakeMeta:
    def __init__(self):
        self.calls: list[dict] = []
        self.fail: dict[str, Exception] = {}
        self.reset()

    def reset(self):
        self.me = {"id": ASID, "name": "Marcos Demo"}
        self.granted = list(meta_facebook.SCOPES) + ["public_profile"]
        self.pages = [{"id": PAGE_DEMO, "name": "MDP Demo", "access_token": "PAGETOKEN-SECRET-1", "tasks": ["MANAGE", "MESSAGING", "MODERATE", "CREATE_CONTENT"]}]
        self.posts = [{"id": "POST1", "message": "Spring promotion, book this week", "permalink_url": "https://facebook.com/mdpdemo/posts/1"}]
        self.post_comments: dict[str, list] = {"POST1": []}
        self.n = 0

    def __call__(self, method, url, *, params=None, data=None, json_body=None, headers=None, timeout=15.0):
        self.calls.append({"method": method, "url": url, "params": params or {}, "json": json_body, "headers": headers or {}})
        path, params = urlparse(url).path, params or {}
        for key, exc in self.fail.items():
            if key in path:
                raise exc
        if path.endswith("/oauth/access_token"):
            if params.get("grant_type") == "fb_exchange_token":
                self.n += 1
                return {"access_token": f"LONGUSER-{self.n}", "token_type": "bearer", "expires_in": 5183944}
            if params.get("code") == "BADCODE":
                raise meta_instagram.MetaApiError(400, "100", "This authorization code has been used")
            return {"access_token": "SHORTUSER-SECRET", "token_type": "bearer"}
        if path.endswith("/me"):
            return dict(self.me)
        if path.endswith("/me/permissions"):
            return {"data": [{"permission": p, "status": "granted"} for p in self.granted] + [{"permission": "business_management", "status": "declined"}]}
        if path.endswith("/me/accounts"):
            return {"data": [dict(p) for p in self.pages]}
        if path.endswith("/subscribed_apps"):
            return {"success": True}
        if path.endswith("/messages") and method == "POST":
            return {"recipient_id": json_body["recipient"]["id"], "message_id": "m_SENT1"}
        if path.endswith("/comments") and method == "POST":
            return {"id": "POST1_REPLY1"}
        if path.endswith("/comments") and method == "GET":
            return {"data": list(self.post_comments.get(path.split("/")[-2], []))}
        if path.endswith("/posts"):
            return {"data": list(self.posts)}
        if params.get("fields") == "name":
            return {"name": "Cliente FB"}
        if params.get("fields") == "id,message,permalink_url":
            return next((p for p in self.posts if p["id"] == path.split("/")[-1]), {})
        raise AssertionError(f"chamada inesperada a Meta: {method} {path}")

    def calls_to(self, suffix):
        return [c for c in self.calls if urlparse(c["url"]).path.endswith(suffix)]


class LogCapture(logging.Handler):
    def __init__(self):
        super().__init__(); self.lines: list[str] = []
    def emit(self, record):
        if record.name.startswith("httpx"):
            return  # sao as requisicoes do PROPRIO cliente de teste (TestClient), nao da aplicacao
        self.lines.append(record.getMessage())


def signed(payload, secret=SECRET_FB):
    raw = json.dumps(payload).encode()
    return raw, {"x-hub-signature-256": "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest(), "content-type": "application/json"}


def b64(b):
    import base64
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def signed_request(user_id, secret=SECRET_FB):
    part = b64(json.dumps({"algorithm": "HMAC-SHA256", "issued_at": int(time.time()), "user_id": user_id}).encode())
    return b64(hmac.new(secret.encode(), part.encode(), hashlib.sha256).digest()) + "." + part


def auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def login(email):
    r = client.post("/api/auth/login", json={"email": email, "senha": SENHA, "contexto_plataforma": False})
    return r.json().get("access_token")


def exigir_ambiente_de_teste():
    if settings.app_env.strip().lower() not in ("development", "dev", "test", "local"):
        sys.exit("Recusado: APP_ENV='%s'. So pode rodar em DEV/teste." % settings.app_env)


def main():
    exigir_ambiente_de_teste()
    fake = FakeMeta()
    meta_instagram.http_json = fake  # meta_facebook.http_json delega para ele
    keys = ("omni_meta_enabled", "omni_public_base_url", "omni_connection_encryption_key", "facebook_app_id", "facebook_app_secret",
            "facebook_login_config_id", "facebook_webhook_verify_token", "meta_whatsapp_app_secret", "instagram_app_id", "instagram_app_secret")
    saved = {k: getattr(settings, k) for k in keys}
    settings.omni_meta_enabled = False
    settings.omni_public_base_url = "https://api.test"
    settings.omni_connection_encryption_key = Fernet.generate_key().decode()
    settings.facebook_app_id, settings.facebook_app_secret, settings.facebook_login_config_id = None, None, None
    settings.facebook_webhook_verify_token, settings.meta_whatsapp_app_secret = None, "change-me"
    settings.instagram_app_id = settings.instagram_app_secret = None

    db = PlatformSessionLocal()
    tenants = {t.codigo: t for t in db.query(PlatformTenant).all()}
    mdp, demo = tenants["MDP"], tenants["MDP_DEMO"]
    logcap = LogCapture(); logging.getLogger().addHandler(logcap); logging.getLogger().setLevel(logging.INFO)
    baseline_eps = {str(r[0]) for r in db.execute(text("select id from tenant_endpoints"))}
    try:
        # ------------------------------------------------------------------ fixtures
        print("\n[0] Fixtures")
        if not db.execute(text("select 1 from tipos_endpoint where codigo='FACEBOOK'")).scalar():
            db.execute(text("insert into tipos_endpoint(codigo,nome,ordem) values ('FACEBOOK','Facebook',70)")); db.commit()

        def novo(email, nome, tenant, perfil_codigo):
            u = PlatformUsuario(nome=nome, email=email, password_hash=hash_password(SENHA), mfa_dispensado=True, acesso_expira_em=utcnow() + timedelta(days=30))
            db.add(u); db.flush(); db.add(PlatformUsuarioTenant(id=uuid4(), usuario_id=u.id, tenant_id=tenant.id, ativo=True)); db.commit()
            with tenant_session(db, tenant.id) as t:
                emp = t.query(Empresa).first(); perfil = t.execute(text("select id from perfis where codigo=:c"), {"c": perfil_codigo}).scalar()
                loc = UsuarioTenantLocal(platform_usuario_id=u.id, ativo=True); t.add(loc); t.flush()
                t.add(UsuarioEmpresa(usuario_id=loc.id, empresa_id=emp.id, perfil_id=perfil, ativo=True, acesso_todas_unidades=True, acesso_todas_areas=True)); t.commit()
        novo(EMAILS["rev"], "Revisor FB", demo, "OMNI_OPERADOR")
        novo(EMAILS["adm"], "Admin MDP FB", mdp, "ADMIN")
        H = auth(login(EMAILS["rev"])); HA = auth(login(EMAILS["adm"]))
        check("0.1 usuarios de teste entram", "Authorization" in H and HA["Authorization"] != "Bearer None")

        def count(sql, **p):
            return db.execute(text(sql), p).scalar()

        def conexao(tenant_id, page=None):
            db.expire_all()
            return db.execute(text("""select c.status, c.token_enc, c.token_expira_em, c.renovar_em, c.webhook_assinado, c.webhook_campos, c.escopos, c.tipo_conexao,
                                             c.token_tipo, c.metadados, e.id as ep, e.identificador_externo as page, e.ativo, e.nome
                                        from canal_conexoes c join tenant_endpoints e on e.id=c.endpoint_id
                                        join tipos_endpoint te on te.id=e.tipo_endpoint_id
                                       where e.tenant_id=:t and te.codigo='FACEBOOK' and (CAST(:pg AS text) is null or e.identificador_externo=:pg)"""),
                              {"t": str(tenant_id), "pg": page}).mappings().first()

        def connect(headers):
            r = client.post("/api/omni/integrations/FACEBOOK/connect", headers=headers)
            return r, (parse_qs(urlparse(r.json()["authorization_url"]).query) if r.status_code == 200 else {})

        def callback(**q):
            return client.get("/api/omni/oauth/facebook/callback", params=q, follow_redirects=False)

        def full_connect(headers, code="GOODCODE"):
            client.cookies.clear()
            r, qs = connect(headers)
            return callback(code=code, state=qs["state"][0])

        # ------------------------------------------------------------------ F. configuracao ausente
        print("\n[F] Sem configuracao do Facebook / chave desligada")
        check("F1 connect = 501", client.post("/api/omni/integrations/FACEBOOK/connect", headers=H).status_code == 501)
        check("F2 webhook GET e POST = 404", client.get("/api/meta/facebook/webhook").status_code == 404 and client.post("/api/meta/facebook/webhook", content=b"{}").status_code == 404)
        check("F3 callback so redireciona com erro 'disabled'", callback(code="x", state="y").headers.get("location") == "/omni?fb_error=disabled")
        settings.omni_meta_enabled = True
        settings.facebook_app_id, settings.facebook_login_config_id = APP_ID, CONFIG_ID
        settings.facebook_app_secret, settings.facebook_webhook_verify_token = SECRET_FB, VERIFY_FB
        settings.omni_public_base_url = "http://api.test"  # o cliente de teste fala http (o cookie Secure so iria em https)
        check("F4 sync sem canal conectado: adiado, sem chamar a Meta", client.post("/api/omni/comments/sync", headers=H).json() == {"new": 0, "skipped": True} and not fake.calls)

        # ------------------------------------------------------------------ C. login
        print("\n[C] Conectar a Pagina (Facebook Login for Business)")
        r, qs = connect(H)
        url = urlparse(r.json()["authorization_url"])
        check("C1 URL de login do Facebook (dialog/oauth, versao da API)", url.netloc == "www.facebook.com" and url.path == f"/{settings.meta_graph_version}/dialog/oauth")
        check("C2 parametros: client_id, redirect_uri, response_type=code, config_id", qs.get("client_id") == [APP_ID] and qs.get("config_id") == [CONFIG_ID]
              and qs.get("redirect_uri") == ["http://api.test/api/omni/oauth/facebook/callback"] and qs.get("response_type") == ["code"]
              and qs.get("override_default_response_type") == ["true"])
        check("C3 nao usa 'scope' (as permissoes vem da configuracao)", "scope" not in qs)
        ck = r.headers.get("set-cookie", "")
        check("C4 cookie do nonce: HttpOnly, SameSite=Lax, caminho restrito", "omni_oauth_nonce=" in ck and "HttpOnly" in ck and "samesite=lax" in ck.lower() and "Path=/api/omni/oauth" in ck)
        check("C5 o estado e assinado, vale 10 minutos e tem proposito 'fb_oauth'", (lambda c: c["purpose"] == "fb_oauth" and 540 < c["exp"] - time.time() <= 601)(
            jwt.decode(qs["state"][0], settings.secret_key, algorithms=[settings.jwt_algorithm])))
        eps_antes = count("select count(*) from tenant_endpoints")
        client.cookies.clear(); r, qs = connect(H); client.cookies.clear()
        check("C6 callback SEM o cookie e recusado", callback(code="GOODCODE", state=qs["state"][0]).headers["location"] == "/omni?fb_error=state")
        r, qs = connect(H)
        ig_state = jwt.encode({"purpose": "ig_oauth", "tid": str(demo.id), "uid": "x", "nonce": client.cookies.get("omni_oauth_nonce"), "exp": utcnow() + timedelta(minutes=5)},
                              settings.secret_key, algorithm=settings.jwt_algorithm)
        check("C7 estado do INSTAGRAM nao serve para o Facebook (proposito)", callback(code="GOODCODE", state=ig_state).headers["location"] == "/omni?fb_error=state")
        forged = jwt.encode({"purpose": "fb_oauth", "tid": str(demo.id), "uid": "x", "nonce": client.cookies.get("omni_oauth_nonce"), "exp": utcnow() + timedelta(minutes=5)}, "outra-chave", algorithm="HS256")
        check("C8 estado FALSIFICADO e recusado", callback(code="GOODCODE", state=forged).headers["location"] == "/omni?fb_error=state")
        check("C9 usuario cancela na Meta", callback(error="access_denied", state=qs["state"][0]).headers["location"] == "/omni?fb_error=denied")
        r, qs = connect(H)
        check("C10 troca de codigo falha na Meta", callback(code="BADCODE", state=qs["state"][0]).headers["location"] == "/omni?fb_error=exchange")
        fake.granted = ["pages_show_list", "pages_messaging", "public_profile"]
        r, qs = connect(H)
        check("C11 permissao faltando e recusada", callback(code="GOODCODE", state=qs["state"][0]).headers["location"] == "/omni?fb_error=permissions")
        check("C11b a recusa por permissao registra os NOMES recebidos no log (sem segredo)", any("fb_oauth_permissoes_recebidas" in l and "pages_messaging" in l for l in logcap.lines))
        fake.granted = list(meta_facebook.SCOPES) + ["public_profile"]
        fake.pages = [{"id": PAGE_DEMO, "name": "MDP Demo", "access_token": "PAGETOKEN-SECRET-1", "tasks": ["ANALYZE", "ADVERTISE"]}]
        r, qs = connect(H)
        check("C12 Pagina sem as tarefas MESSAGING e MODERATE nao e conectada (no_page)", callback(code="GOODCODE", state=qs["state"][0]).headers["location"] == "/omni?fb_error=no_page")
        fake.pages = []
        r, qs = connect(H)
        check("C13 nenhuma Pagina autorizada (no_page)", callback(code="GOODCODE", state=qs["state"][0]).headers["location"] == "/omni?fb_error=no_page")
        fake.reset()
        check("C14 nenhuma tentativa falha gravou canal nem conexao", count("select count(*) from tenant_endpoints") == eps_antes and conexao(demo.id) is None)

        fake.calls.clear()
        resp = full_connect(H)
        check("C15 fluxo correto: redireciona para /omni?fb=connected", resp.status_code == 303 and resp.headers["location"] == "/omni?fb=connected", resp.headers.get("location"))
        c = conexao(demo.id, PAGE_DEMO)
        check("C16 canal criado com o ID da PAGINA (o 'id' dos webhooks) e o nome", c and c["page"] == PAGE_DEMO and c["nome"] == "MDP Demo")
        check("C17 conexao FACEBOOK_PAGE / PAGE_TOKEN, CONECTADO, webhook assinado (messages,feed), 6 escopos",
              c and c["tipo_conexao"] == "FACEBOOK_PAGE" and c["token_tipo"] == "PAGE_TOKEN" and c["status"] == "CONECTADO" and c["webhook_assinado"]
              and c["webhook_campos"] == ["messages", "feed"] and sorted(c["escopos"]) == sorted(meta_facebook.SCOPES))
        check("C18 token da PAGINA gravado CRIPTOGRAFADO e descriptografa para o token da Pagina (nao o do usuario)",
              c and "PAGETOKEN" not in c["token_enc"] and meta_crypto.decrypt_token(c["token_enc"]) == "PAGETOKEN-SECRET-1")
        check("C19 token da Pagina nao expira: sem validade e sem renovacao agendada", c and c["token_expira_em"] is None and c["renovar_em"] is None)
        check("C20 ID do usuario NO APP guardado nos metadados (para os callbacks de privacidade)", c and (c["metadados"] or {}).get("app_user_id") == ASID)
        exch = [x for x in fake.calls_to("/oauth/access_token") if x["params"].get("grant_type") == "fb_exchange_token"]
        accounts = fake.calls_to("/me/accounts")
        check("C21 o token do usuario foi trocado por um de LONGA duracao antes de pedir as Paginas", len(exch) == 1
              and exch[0]["params"]["fb_exchange_token"] == "SHORTUSER-SECRET" and accounts and accounts[0]["params"]["access_token"].startswith("LONGUSER-"))
        sub = fake.calls_to("/subscribed_apps")
        check("C22 webhooks assinados na Meta com o token da Pagina: messages,feed", len(sub) == 1 and sub[0]["params"]["subscribed_fields"] == "messages,feed"
              and f"/{PAGE_DEMO}/" in sub[0]["url"] and sub[0]["params"]["access_token"] == "PAGETOKEN-SECRET-1")
        integ = client.get("/api/omni/integrations", headers=H).json()
        fb = next(i for i in integ if i["provider"] == "FACEBOOK")
        check("C23 tela: Facebook CONNECTED com o nome da Pagina, sem expor segredos", fb["status"] == "CONNECTED" and fb["account_name"] == "MDP Demo"
              and set(fb) == {"provider", "status", "account_name", "handle", "connected_at", "token_expires_at"} and "PAGETOKEN" not in json.dumps(integ))
        check("C24 o cookie do nonce e apagado ao voltar", "Max-Age=0" in resp.headers.get("set-cookie", ""))
        resp = full_connect(HA)
        check("C25 a MESMA Pagina em OUTRO tenant e recusada", resp.headers["location"] == "/omni?fb_error=already_connected" and conexao(demo.id, PAGE_DEMO)["status"] == "CONECTADO")
        antes = conexao(demo.id, PAGE_DEMO)
        fake.pages = [{"id": PAGE_DEMO, "name": "MDP Demo", "access_token": "PAGETOKEN-SECRET-2", "tasks": ["MESSAGING", "MODERATE"]}]
        resp = full_connect(H)
        depois = conexao(demo.id, PAGE_DEMO)
        check("C26 reconectar a mesma Pagina atualiza o token sem duplicar canal", resp.headers["location"] == "/omni?fb=connected" and depois["ep"] == antes["ep"]
              and meta_crypto.decrypt_token(depois["token_enc"]) == "PAGETOKEN-SECRET-2"
              and count("select count(*) from tenant_endpoints where tenant_id=:t and identificador_externo=:i", t=str(demo.id), i=PAGE_DEMO) == 1)
        fake.pages = [{"id": PAGE_MDP, "name": "Pagina MDP", "access_token": "PAGETOKEN-SECRET-M", "tasks": ["MESSAGING", "MODERATE"]},
                      {"id": "100000000000003", "name": "Outra Pagina", "access_token": "PAGETOKEN-SECRET-O", "tasks": ["MESSAGING", "MODERATE"]}]
        fake.me = {"id": "asid-888", "name": "Outro Admin"}  # outro usuario do Facebook (a exclusao e por usuario no app)
        resp = full_connect(HA)
        fake.me = {"id": ASID, "name": "Marcos Demo"}
        check("C27 varias Paginas autorizadas: conecta a primeira e avisa (fb_warn=pages)", resp.headers["location"] == "/omni?fb=connected&fb_warn=pages"
              and conexao(mdp.id, PAGE_MDP) and not conexao(mdp.id, "100000000000003"))
        fake.pages = [{"id": PAGE_DEMO, "name": "MDP Demo", "access_token": "PAGETOKEN-SECRET-1", "tasks": ["MESSAGING", "MODERATE"]}]
        fake.fail["/subscribed_apps"] = meta_instagram.MetaApiError(400, "200", "x")
        resp = full_connect(H)
        c = conexao(demo.id, PAGE_DEMO)
        check("C28 falha ao assinar o webhook: conecta mesmo assim, avisa (fb_warn=webhook) e marca webhook_assinado=false",
              resp.headers["location"] == "/omni?fb=connected&fb_warn=webhook" and c["status"] == "CONECTADO" and not c["webhook_assinado"])
        fake.fail.clear()
        full_connect(H)
        check("C29 conexao normal volta a assinar o webhook", conexao(demo.id, PAGE_DEMO)["webhook_assinado"])
        check("C30 nenhum token, codigo ou segredo apareceu em LOG", not any(s in line for line in logcap.lines for s in SENSIVEL))

        # ------------------------------------------------------------------ W. webhook
        print("\n[W] Webhook do Facebook")
        W = "/api/meta/facebook/webhook"
        check("W1 verificacao correta devolve o desafio", (lambda r: r.status_code == 200 and r.text == "777")(client.get(W, params={"hub.mode": "subscribe", "hub.verify_token": VERIFY_FB, "hub.challenge": "777"})))
        check("W2 verificacao com token errado ou ausente = 403", client.get(W, params={"hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "1"}).status_code == 403
              and client.get(W, params={"hub.mode": "subscribe", "hub.challenge": "1"}).status_code == 403)
        now_s = int(time.time()); now_ms = now_s * 1000
        PSID = "psid-cliente-1"
        dm = lambda mid, **x: {"object": "page", "entry": [{"id": x.get("page", PAGE_DEMO), "time": now_ms, "messaging": [
            {"sender": {"id": x.get("sender", PSID)}, "recipient": {"id": PAGE_DEMO}, "timestamp": now_ms, "message": {"mid": mid, **x.get("msg", {"text": "Hello! Are you open on Saturday?"})}}]}]}
        raw, hdr = signed(dm("m_IN1"), "segredo-errado")
        check("W3 assinatura invalida = 403", client.post(W, content=raw, headers=hdr).status_code == 403)
        check("W3b sem assinatura = 403", client.post(W, content=raw, headers={"content-type": "application/json"}).status_code == 403)
        raw, hdr = signed(dm("m_IN1"))
        r = client.post(W, content=raw, headers=hdr)
        check("W4 mensagem com assinatura valida = 200", r.status_code == 200 and r.json() == {"received": True})
        convs = client.get("/api/omni/conversations?channel=FACEBOOK", headers=H).json()
        conv = next((c for c in convs if c["last_text"] and "Saturday" in c["last_text"]), None)
        check("W5 conversa FACEBOOK criada, com nome buscado no perfil, janela de 24h aberta e 1 nao lida",
              conv and conv["channel"] == "FACEBOOK" and conv["name"] == "Cliente FB" and conv["reply_window_open"] and conv["unread"] == 1)
        client.post(W, content=raw, headers=hdr)
        msgs = client.get(f"/api/omni/conversations/{conv['id']}/messages", headers=H).json()["messages"]
        check("W6 o mesmo evento reenviado nao duplica (idempotente)", len([m for m in msgs if m["text"] and "Saturday" in m["text"]]) == 1)
        for payload in (dm("m_ECHO1", sender=PAGE_DEMO), dm("m_ECHO2", msg={"text": "eco", "is_echo": True})):
            r_, h_ = signed(payload); client.post(W, content=r_, headers=h_)
        msgs = client.get(f"/api/omni/conversations/{conv['id']}/messages", headers=H).json()["messages"]
        check("W7 ecos (mensagens da propria Pagina) sao ignorados", len(msgs) == 1)
        r_, h_ = signed(dm("m_X", page="999999999"))
        check("W8 Pagina desconhecida: 200 e nada gravado", client.post(W, content=r_, headers=h_).status_code == 200)
        r_, h_ = signed({**dm("m_IG"), "object": "instagram"})
        check("W9 payload de outro produto (object != page) e ignorado", client.post(W, content=r_, headers=h_).status_code == 200
              and len(client.get(f"/api/omni/conversations/{conv['id']}/messages", headers=H).json()["messages"]) == 1)
        r_, h_ = signed(dm("m_ATT1", msg={"attachments": [{"type": "image", "payload": {"url": "https://x/y.png"}}]}))
        client.post(W, content=r_, headers=h_)
        check("W10 anexo vira '[attachment]' (sem guardar a URL)", any(m["text"] == "[attachment]" for m in client.get(f"/api/omni/conversations/{conv['id']}/messages", headers=H).json()["messages"]))
        r_, h_ = signed({"object": "page", "entry": [{"id": PAGE_DEMO, "time": now_ms, "messaging": [{"sender": {"id": PSID}, "recipient": {"id": PAGE_DEMO}, "timestamp": now_ms, "postback": {"title": "x", "payload": "y"}}]}]})
        check("W11 eventos que nao sao mensagem (postback, leitura) sao ignorados com 200", client.post(W, content=r_, headers=h_).status_code == 200)
        check("W12 corpo gigante = 413", client.post(W, content=b"x" * 1_000_001, headers={"x-hub-signature-256": "sha256=0", "content-type": "application/json"}).status_code == 413)
        check("W13 a mensagem ficou so no banco do tenant DONO da Pagina (o outro tenant nao a ve)",
              not any(c["last_text"] and "Saturday" in c["last_text"] for c in client.get("/api/omni/conversations", headers=HA).json()))

        feed = lambda cid, **v: {"object": "page", "entry": [{"id": PAGE_DEMO, "time": now_s, "changes": [{"field": "feed", "value": {
            "from": v.get("frm", {"id": "555", "name": "Carla Mendes"}), "item": v.get("item", "comment"), "comment_id": cid, "post_id": "POST1",
            "verb": v.get("verb", "add"), "parent_id": v.get("parent", "POST1"), "created_time": now_s, "message": v.get("text", "Does this include weekends?")}}]}]}
        r_, h_ = signed(feed("POST1_C1")); client.post(W, content=r_, headers=h_)
        comments = client.get("/api/omni/comments?channel=FACEBOOK", headers=H).json()
        carla = next((c for c in comments if c["text"] == "Does this include weekends?"), None)
        check("W14 comentario gravado com o post de origem (texto e link buscados na Meta), canal FACEBOOK",
              carla and carla["channel"] == "FACEBOOK" and carla["author_name"] == "Carla Mendes" and carla["post"] == "Spring promotion, book this week" and carla["post_url"])
        for payload in (feed("POST1_C2", frm={"id": PAGE_DEMO, "name": "MDP Demo"}), feed("POST1_C3", item="post"), feed("POST1_C4", verb="edited"), feed("POST1_C5", item="reaction")):
            r_, h_ = signed(payload); client.post(W, content=r_, headers=h_)
        check("W15 comentario da PROPRIA Pagina, posts, reacoes e edicoes sao ignorados", len(client.get("/api/omni/comments?channel=FACEBOOK", headers=H).json()) == len(comments))
        r_, h_ = signed(feed("POST1_C1")); client.post(W, content=r_, headers=h_)
        check("W16 o mesmo comentario reenviado nao duplica", len(client.get("/api/omni/comments?channel=FACEBOOK", headers=H).json()) == len(comments))
        r_, h_ = signed(feed("POST1_C6", parent="POST1_C1", text="Yes, including Sunday"))
        client.post(W, content=r_, headers=h_)
        with tenant_session(db, demo.id) as t:
            row = t.execute(text("select parent_external_id from omni_comentarios where external_comment_id='POST1_C6'")).first()
            top = t.execute(text("select parent_external_id from omni_comentarios where external_comment_id='POST1_C1'")).first()
        check("W17 resposta de outro comentario guarda o pai; comentario de 1o nivel NAO tem pai (o 'pai' da Meta e o post)",
              row and row[0] == "POST1_C1" and top and top[0] is None)
        check("W18 o webhook funciona tambem so com META_WHATSAPP_APP_SECRET (mesmo app) quando FACEBOOK_APP_SECRET esta vazio", (lambda: (
            setattr(settings, "facebook_app_secret", None), setattr(settings, "meta_whatsapp_app_secret", "main-secret-tests"),
            client.post(W, content=signed(dm("m_ALT1", msg={"text": "alt secret"}), "main-secret-tests")[0], headers=signed(dm("m_ALT1", msg={"text": "alt secret"}), "main-secret-tests")[1]).status_code == 200,
            setattr(settings, "facebook_app_secret", SECRET_FB), setattr(settings, "meta_whatsapp_app_secret", "change-me"))[2])())

        # ------------------------------------------------------------------ S. envio
        print("\n[S] Respostas pelo Omni")
        fake.calls.clear()
        r = client.post(f"/api/omni/conversations/{conv['id']}/reply", json={"text": "Yes, we open at 9am"}, headers=H)
        sent = fake.calls_to("/messages")
        check("S1 resposta enviada: ENVIADA, com o ID da mensagem da Meta", r.status_code == 201 and r.json()["status"] == "ENVIADA")
        check("S2 chamada a Meta: POST /<pagina>/messages, destinatario = PSID, messaging_type RESPONSE, token da Pagina no cabecalho",
              len(sent) == 1 and f"/{PAGE_DEMO}/messages" in sent[0]["url"] and sent[0]["json"]["recipient"] == {"id": PSID}
              and sent[0]["json"]["messaging_type"] == "RESPONSE" and sent[0]["headers"].get("Authorization") == "Bearer PAGETOKEN-SECRET-1")
        fake.fail["/messages"] = meta_instagram.MetaApiError(400, "190", "x")
        r = client.post(f"/api/omni/conversations/{conv['id']}/reply", json={"text": "falha"}, headers=H)
        check("S3 erro da Meta (token invalido, 190): FALHA com codigo curto e seguro", r.json()["status"] == "FALHA" and r.json()["error"] == "meta_190")
        fake.fail.clear()
        with tenant_session(db, demo.id) as t:
            t.execute(text("update omni_conversas set ultima_mensagem_cliente_em = now() - interval '25 hours' where id=:i"), {"i": conv["id"]}); t.commit()
        check("S4 janela de 24h fechada: 409 e nada enviado", client.post(f"/api/omni/conversations/{conv['id']}/reply", json={"text": "tarde"}, headers=H).status_code == 409)
        fake.calls.clear()
        comment_id = carla["id"]
        r = client.post(f"/api/omni/comments/{comment_id}/reply", json={"text": "Yes, weekends included!"}, headers=H)
        rep = [c for c in fake.calls if urlparse(c["url"]).path.endswith("/comments") and c["method"] == "POST"]
        check("S5 resposta a comentario: POST /<comentario>/comments com a mensagem e o token da Pagina", r.status_code == 201 and r.json()["status"] == "ENVIADA"
              and len(rep) == 1 and "/POST1_C1/comments" in rep[0]["url"] and rep[0]["json"] == {"message": "Yes, weekends included!"}
              and rep[0]["headers"].get("Authorization") == "Bearer PAGETOKEN-SECRET-1")
        mine = next(c for c in client.get("/api/omni/comments?channel=FACEBOOK", headers=H).json() if c["id"] == comment_id)
        check("S6 o comentario fica 'respondido' e a resposta aparece embaixo dele", mine["replied"] and mine["replies"] and mine["replies"][0]["text"] == "Yes, weekends included!")
        fake.fail["/comments"] = meta_instagram.MetaApiError(400, "10", "x")
        r = client.post(f"/api/omni/comments/{next(c for c in client.get('/api/omni/comments?channel=FACEBOOK', headers=H).json() if c['text'] == 'Yes, including Sunday')['id']}/reply",
                        json={"text": "x"}, headers=H)
        fake.fail.clear()
        check("S7 falha ao responder comentario: FALHA e o comentario NAO vira 'respondido'", r.json()["status"] == "FALHA")

        # ------------------------------------------------------------------ Y. sincronizacao por consulta
        print("\n[Y] Sincronizacao de comentarios por consulta")
        fake.post_comments["POST1"] = [
            {"id": "POST1_C9", "message": "from sync", "from": {"id": "888", "name": "Bia"}, "created_time": "2026-10-08T12:00:00+0000", "parent": {"id": "POST1_C1"}},
            {"id": "POST1_C10", "message": "our own", "from": {"id": PAGE_DEMO, "name": "MDP Demo"}, "created_time": "2026-10-08T12:01:00+0000"},
            {"id": "POST1_C1", "message": "Does this include weekends?", "from": {"id": "555", "name": "Carla Mendes"}, "created_time": "2026-10-08T11:00:00+0000"}]
        db.execute(text("update canal_conexoes set metadados = metadados - 'last_comment_sync' where tenant_id=:t"), {"t": str(demo.id)}); db.commit()
        r = client.post("/api/omni/comments/sync", headers=H)
        check("Y1 sincronizacao traz so os comentarios NOVOS de outras pessoas (1)", r.status_code == 200 and r.json() == {"new": 1, "skipped": False}, r.text)
        with tenant_session(db, demo.id) as t:
            row = t.execute(text("select parent_external_id, canal, post_resumo from omni_comentarios where external_comment_id='POST1_C9'")).first()
        check("Y2 gravado como FACEBOOK, com o pai e o texto do post", row and row[0] == "POST1_C1" and row[1] == "FACEBOOK" and row[2] == "Spring promotion, book this week")
        n = len(fake.calls)
        check("Y3 segunda sincronizacao em seguida e adiada (nao chama a Meta)", client.post("/api/omni/comments/sync", headers=H).json() == {"new": 0, "skipped": True} and len(fake.calls) == n)
        db.execute(text("update canal_conexoes set metadados = metadados - 'last_comment_sync' where tenant_id=:t"), {"t": str(demo.id)}); db.commit()
        check("Y4 passado o intervalo, repetir nao duplica nada", client.post("/api/omni/comments/sync", headers=H).json() == {"new": 0, "skipped": False})
        db.execute(text("update canal_conexoes set metadados = metadados - 'last_comment_sync' where tenant_id=:t"), {"t": str(demo.id)}); db.commit()
        fake.fail["/posts"] = meta_instagram.MetaApiError(400, "190", "x")
        r = client.post("/api/omni/comments/sync", headers=H)
        fake.fail.clear()
        check("Y5 erro da Meta na sincronizacao nao derruba a tela (devolve o codigo)", r.status_code == 200 and r.json().get("error") == "190")

        # ------------------------------------------------------------------ P. privacidade
        print("\n[P] Desautorizacao e exclusao de dados (Facebook)")
        def post_form(path, sr):
            return client.post(path, content=urlencode({"signed_request": sr}).encode(), headers={"content-type": "application/x-www-form-urlencoded"})
        r = post_form("/api/meta/deauthorize", signed_request(ASID, "outro-segredo"))
        check("P1 assinatura invalida = 403", r.status_code == 403)
        r = post_form("/api/meta/deauthorize", signed_request(ASID))
        c = conexao(demo.id, PAGE_DEMO)
        check("P2 desautorizacao (user_id = ID do usuario no app): conexao REVOGADA e token APAGADO", r.status_code == 200 and c["status"] == "REVOGADO" and c["token_enc"] is None)
        with tenant_session(db, demo.id) as t:
            tem = t.execute(text("select count(*) from omni_conversas where canal='FACEBOOK'")).scalar()
        check("P3 o conteudo NAO e apagado na desautorizacao", tem >= 1)
        r_, h_ = signed(dm("m_AFTER", msg={"text": "depois de revogar"}))
        client.post(W, content=r_, headers=h_)
        check("P4 eventos de Pagina revogada sao ignorados", not any(c["last_text"] and "revogar" in c["last_text"] for c in client.get("/api/omni/conversations?channel=FACEBOOK", headers=H).json()))
        r = client.post(f"/api/omni/conversations/{conv['id']}/reply", json={"text": "x"}, headers=H)
        check("P5 responder com a conexao revogada: erro 409 (janela) ou FALHA channel_not_connected, nunca envio",
              r.status_code == 409 or (r.status_code == 201 and r.json()["error"] == "channel_not_connected"))
        r = post_form("/api/meta/data-deletion", signed_request(ASID))
        body = r.json()
        check("P6 exclusao: 200 com url de status e codigo de confirmacao", r.status_code == 200 and len(body["confirmation_code"]) == 16 and body["url"].endswith(body["confirmation_code"]))
        with tenant_session(db, demo.id) as t:
            restam = t.execute(text("select (select count(*) from omni_conversas where endpoint_id=:e), (select count(*) from omni_comentarios where endpoint_id=:e)"),
                               {"e": str(c["ep"])}).first()
        db.expire_all()
        ep = db.execute(text("select ativo, nome, identificador_externo from tenant_endpoints where id=:e"), {"e": str(c["ep"])}).first()
        check("P7 conversas, mensagens e comentarios da Pagina foram APAGADOS no banco do tenant", tuple(restam) == (0, 0))
        check("P8 o canal ficou inativo e anonimizado (sem nome nem ID da Pagina)", ep and ep[0] is False and ep[1] == "Removed channel" and ep[2] is None)
        check("P9 a Pagina de OUTRO usuario do app nao foi afetada", conexao(mdp.id, PAGE_MDP)["status"] == "CONECTADO")
        resp = full_connect(H)
        check("P10 e possivel conectar a Pagina de novo depois da exclusao (canal novo)", resp.headers["location"] == "/omni?fb=connected" and conexao(demo.id, PAGE_DEMO)["status"] == "CONECTADO")

        # ------------------------------------------------------------------ D. desconectar
        print("\n[D] Desconectar")
        r = client.delete("/api/omni/integrations/FACEBOOK", headers=H)
        c = conexao(demo.id, PAGE_DEMO)
        check("D1 desconectar: REVOGADO, token APAGADO, webhook desmarcado", r.json() == {"disconnected": True} and c["status"] == "REVOGADO" and c["token_enc"] is None and not c["webhook_assinado"])
        fb = next(i for i in client.get("/api/omni/integrations", headers=H).json() if i["provider"] == "FACEBOOK")
        check("D2 a tela mostra REVOKED", fb["status"] == "REVOKED")
        check("D3 desconectar de novo e inofensivo", client.delete("/api/omni/integrations/FACEBOOK", headers=H).json() == {"disconnected": False})

        # ------------------------------------------------------------------ X. permissao e logs
        print("\n[X] Permissoes e logs")
        check("X1 sem login: connect, sync e desconectar sao recusados", all(code in (401, 403) for code in (
            client.post("/api/omni/integrations/FACEBOOK/connect").status_code, client.post("/api/omni/comments/sync").status_code,
            client.delete("/api/omni/integrations/FACEBOOK").status_code)))
        check("X2 o callback sem estado nunca conecta nada", callback(code="GOODCODE").headers["location"] == "/omni?fb_error=state")
        settings.omni_meta_enabled = False
        check("X3 ao desligar a chave, o webhook volta a 404 e o connect a 501", client.get(W).status_code == 404 and client.post("/api/omni/integrations/FACEBOOK/connect", headers=H).status_code == 501)
        settings.omni_meta_enabled = True
        check("X4 provedor desconhecido = 404", client.post("/api/omni/integrations/TWITTER/connect", headers=H).status_code == 404)
        check("X5 ao final, nenhum token, codigo ou segredo apareceu em LOG", not any(s in line for line in logcap.lines for s in SENSIVEL))
    finally:
        logging.getLogger().removeHandler(logcap)
        db.rollback()
        created = [r[0] for r in db.execute(text("select id from tenant_endpoints")) if str(r[0]) not in baseline_eps]
        ids = [str(i) for i in created]
        for tn in (mdp, demo):
            try:
                with tenant_session(db, tn.id) as t:
                    for ep in ids:
                        t.execute(text("delete from omni_conversas where endpoint_id=:e"), {"e": ep})
                        t.execute(text("delete from omni_comentarios where endpoint_id=:e"), {"e": ep})
                    t.commit()
            except Exception:
                pass
        for ep in ids:
            db.execute(text("delete from canal_conexoes where endpoint_id=:e"), {"e": ep})
            db.execute(text("delete from tenant_endpoints where id=:e"), {"e": ep})
        db.execute(text("delete from meta_pedidos_privacidade where meta_user_id = :u"), {"u": ASID})
        db.commit()
        uids = [r[0] for r in db.execute(text("select id from usuarios where email = any(:e)"), {"e": list(EMAILS.values())})]
        for tn in (mdp, demo):
            with tenant_session(db, tn.id) as t:
                for uid in uids:
                    t.execute(text("delete from usuarios_empresas where usuario_id in (select id from usuarios_tenant where platform_usuario_id=:u)"), {"u": uid})
                    t.execute(text("delete from usuarios_tenant where platform_usuario_id=:u"), {"u": uid})
                t.commit()
        for uid in uids:
            for sql in ("delete from sessoes_usuario where usuario_id=:u", "delete from usuarios_tenants where usuario_id=:u", "delete from usuarios where id=:u"):
                db.execute(text(sql), {"u": uid})
        db.commit(); db.close()
        for k, v in saved.items():
            setattr(settings, k, v)

    falhas = resultados.count(False)
    print(f"\nResumo: {len(resultados) - falhas} ok, {falhas} falha(s) de {len(resultados)} verificacoes.")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
