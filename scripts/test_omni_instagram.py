"""
Teste automatico do backend do Instagram no Omni, com uma META SIMULADA (nenhuma chamada real sai daqui).

ONDE RODAR: SOMENTE em banco de TESTE/DEV (trava por APP_ENV). Cria e REMOVE usuarios @exemplo-teste.com.br, canais e dados
de teste nos tenants MDP e MDP_DEMO. Nao imprime tokens, codigos nem senhas.

Uso:  python scripts/test_omni_instagram.py
Pre-requisitos: migrations 010/006 aplicadas; tenants MDP e MDP_DEMO provisionados (como nos outros testes).
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
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import jwt
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

import omni_refresh_tokens
from app.config import settings
from app.database import PlatformSessionLocal, tenant_session
from app.main import app
from app.models.auth import UsuarioEmpresa, UsuarioTenantLocal
from app.models.empresa import Empresa
from app.models.platform_auth import PlatformTenant, PlatformUsuario, PlatformUsuarioTenant
from app.security.password import hash_password
from app.services import meta_crypto, meta_instagram, omni_store
from app.services.auth_service import utcnow

SENHA = "SenhaTeste#12345"
EMAILS = {"rev": "ig.revisor@exemplo-teste.com.br", "adm": "ig.admin@exemplo-teste.com.br"}
IG_DEMO, IG_MDP = "17841400000000001", "17841499999999999"
SECRET_IG, SECRET_MAIN, VERIFY = "ig-secret-for-tests", "main-secret-for-tests", "verify-token-for-tests"
resultados: list[bool] = []
client = TestClient(app)


def check(nome, cond, detalhe=""):
    resultados.append(bool(cond))
    print(("  OK   " if cond else "  FALHA") + f"  {nome}" + (f"  [{detalhe}]" if detalhe and not cond else ""))


# ----------------------------------------------------------------------------- Meta simulada
class FakeMeta:
    def __init__(self):
        self.calls: list[dict] = []
        self.me = {"user_id": IG_DEMO, "username": "mdpdemo", "name": "MDP Demo", "account_type": "BUSINESS"}
        self.permissions = ",".join(meta_instagram.SCOPES)
        self.fail: dict[str, Exception] = {}
        self.media = [{"id": "M1", "caption": "Spring promotion, book this week", "permalink": "https://instagram.com/p/AAA"}]
        self.comments = {"M1": []}
        self.n = 0

    def __call__(self, method, url, *, params=None, data=None, json_body=None, headers=None, timeout=15.0):
        self.calls.append({"method": method, "url": url, "params": params or {}, "data": data or {}, "json": json_body, "headers": headers or {}})
        path = urlparse(url).path
        for key, exc in self.fail.items():
            if key in path:
                raise exc
        if url == meta_instagram.OAUTH_TOKEN:
            if data["code"] == "BADCODE":
                raise meta_instagram.MetaApiError(400, "400", "Matching code was not found or was already used")
            return {"data": [{"access_token": "SHORTTOKEN-SECRET", "user_id": "appscoped999", "permissions": self.permissions}]}
        if path.endswith("/refresh_access_token"):
            self.n += 1
            return {"access_token": f"REFRESHED-{self.n}", "token_type": "bearer", "expires_in": 5183944}
        if path.endswith("/access_token"):
            self.n += 1
            return {"access_token": f"LONGTOKEN-{self.n}", "token_type": "bearer", "expires_in": 5183944}
        if path.endswith("/me"):
            return {"data": [dict(self.me)]}  # a doc mostra {"data":[...]}: o cliente aceita tambem o objeto simples
        if path.endswith("/subscribed_apps"):
            return {"success": True}
        if path.endswith("/messages"):
            return {"recipient_id": json_body["recipient"]["id"], "message_id": "mid.SENT1"}
        if path.endswith("/replies"):
            return {"id": "17873440459141029"}
        if path.endswith("/media"):
            return {"data": list(self.media)}
        if path.endswith("/comments"):
            return {"data": list(self.comments.get(path.split("/")[-2], []))}
        if (params or {}).get("fields") == "name,username":
            return {"name": "Cliente Teste", "username": "cliente.teste"}
        if (params or {}).get("fields") == "id,caption,permalink":
            return next((m for m in self.media if m["id"] == path.split("/")[-1]), {})
        raise AssertionError(f"chamada inesperada a Meta: {method} {path}")

    def calls_to(self, suffix):
        return [c for c in self.calls if urlparse(c["url"]).path.endswith(suffix)]


class LogCapture(logging.Handler):
    def __init__(self):
        super().__init__(); self.lines: list[str] = []
    def emit(self, record):
        self.lines.append(record.getMessage())


def signed(payload, secret=SECRET_IG):
    raw = json.dumps(payload).encode()
    return raw, {"x-hub-signature-256": "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest(), "content-type": "application/json"}


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
    meta_instagram.http_json = fake
    saved = {k: getattr(settings, k) for k in ("omni_meta_enabled", "omni_public_base_url", "omni_connection_encryption_key", "instagram_app_id",
                                                 "instagram_app_secret", "instagram_webhook_verify_token", "meta_whatsapp_app_secret")}
    settings.omni_meta_enabled = False
    settings.omni_public_base_url = "https://api.test"
    settings.omni_connection_encryption_key = Fernet.generate_key().decode()
    settings.instagram_app_id, settings.instagram_app_secret = "1043605645256145", SECRET_IG
    settings.instagram_webhook_verify_token, settings.meta_whatsapp_app_secret = VERIFY, SECRET_MAIN

    db = PlatformSessionLocal()
    tenants = {t.codigo: t for t in db.query(PlatformTenant).all()}
    mdp, demo = tenants["MDP"], tenants["MDP_DEMO"]
    logcap = LogCapture(); logging.getLogger().addHandler(logcap); logging.getLogger().setLevel(logging.INFO)
    baseline_eps = {str(r[0]) for r in db.execute(text("select id from tenant_endpoints"))}
    manual_ep = None
    try:
        # ------------------------------------------------------------------ fixtures
        print("\n[0] Fixtures")
        if not db.execute(text("select 1 from tipos_endpoint where codigo='INSTAGRAM'")).scalar():
            db.execute(text("insert into tipos_endpoint(codigo,nome,ordem) values ('INSTAGRAM','Instagram',60)")); db.commit()
        tipo = db.execute(text("select id from tipos_endpoint where codigo='INSTAGRAM'")).scalar()

        def novo(email, nome, tenant, perfil_codigo):
            u = PlatformUsuario(nome=nome, email=email, password_hash=hash_password(SENHA), mfa_dispensado=True, acesso_expira_em=utcnow() + timedelta(days=30))
            db.add(u); db.flush(); db.add(PlatformUsuarioTenant(id=uuid4(), usuario_id=u.id, tenant_id=tenant.id, ativo=True)); db.commit()
            with tenant_session(db, tenant.id) as t:
                emp = t.query(Empresa).first(); perfil = t.execute(text("select id from perfis where codigo=:c"), {"c": perfil_codigo}).scalar()
                loc = UsuarioTenantLocal(platform_usuario_id=u.id, ativo=True); t.add(loc); t.flush()
                t.add(UsuarioEmpresa(usuario_id=loc.id, empresa_id=emp.id, perfil_id=perfil, ativo=True, acesso_todas_unidades=True, acesso_todas_areas=True)); t.commit()
        novo(EMAILS["rev"], "Revisor IG", demo, "OMNI_OPERADOR")
        novo(EMAILS["adm"], "Admin MDP IG", mdp, "ADMIN")
        # cadastro manual antigo do tenant MDP (so @usuario, sem ID): a conexao deve ADOTAR este canal, e nao duplicar
        manual_ep = db.execute(text("""insert into tenant_endpoints (tenant_id, codigo, nome, identificador_publico, tipo_endpoint_id)
                                       values (:t, 'INSTAGRAM_TESTE_ADOCAO', 'Instagram teste (manual)', 'teste.adocao.omni', :tipo) returning id"""),
                               {"t": str(mdp.id), "tipo": str(tipo)}).scalar(); db.commit()
        H = auth(login(EMAILS["rev"])); HA = auth(login(EMAILS["adm"]))
        check("0.1 usuarios de teste entram", "Authorization" in H and HA["Authorization"] != "Bearer None")

        def count(sql, **p):
            return db.execute(text(sql), p).scalar()

        def conexao(tenant_id, ig=None):
            db.expire_all()
            return db.execute(text("""select c.status, c.token_enc, c.token_expira_em, c.webhook_assinado, c.escopos, c.ultimo_erro, e.id as ep,
                                             e.identificador_externo as ig, e.identificador_publico as usr, c.renovar_em
                                        from canal_conexoes c join tenant_endpoints e on e.id=c.endpoint_id
                                       where e.tenant_id=:t and (CAST(:ig AS text) is null or e.identificador_externo=:ig)"""),
                              {"t": str(tenant_id), "ig": ig}).mappings().first()

        def connect(headers):
            r = client.post("/api/omni/integrations/INSTAGRAM/connect", headers=headers)
            return r, (parse_qs(urlparse(r.json()["authorization_url"]).query) if r.status_code == 200 else {})

        def callback(**q):
            return client.get("/api/omni/oauth/instagram/callback", params=q, follow_redirects=False)

        def full_connect(headers, code="GOODCODE"):
            client.cookies.clear()
            r, qs = connect(headers)
            return callback(code=code, state=qs["state"][0])

        # ------------------------------------------------------------------ F. chave desligada
        print("\n[F] Com OMNI_META_ENABLED desligado")
        check("F1 connect = 501", client.post("/api/omni/integrations/INSTAGRAM/connect", headers=H).status_code == 501)
        check("F2 webhook GET e POST = 404 (nem existem para quem chama)", client.get("/api/meta/instagram/webhook").status_code == 404
              and client.post("/api/meta/instagram/webhook", content=b"{}").status_code == 404)
        check("F3 callback so redireciona com erro 'disabled' e nao grava nada", callback(code="x", state="y").headers.get("location") == "/omni?ig_error=disabled")
        check("F4 sync responde 'skipped' sem chamar a Meta", client.post("/api/omni/comments/sync", headers=H).json() == {"new": 0, "skipped": True} and not fake.calls)
        settings.omni_meta_enabled = True

        # ------------------------------------------------------------------ C. OAuth
        print("\n[C] Conectar o Instagram (OAuth)")
        r, qs = connect(H)
        check("C1 connect devolve a URL de autorizacao do Instagram", r.status_code == 200 and r.json()["authorization_url"].startswith("https://www.instagram.com/oauth/authorize?"))
        check("C2 parametros: client_id, redirect_uri, response_type, force_reauth", qs.get("client_id") == ["1043605645256145"]
              and qs.get("redirect_uri") == ["https://api.test/api/omni/oauth/instagram/callback"] and qs.get("response_type") == ["code"] and qs.get("force_reauth") == ["true"])
        check("C3 escopos pedidos = exatamente as 3 permissoes", qs.get("scope") == [",".join(meta_instagram.SCOPES)])
        cookie_hdr = r.headers.get("set-cookie", "")
        check("C4 cookie do nonce: HttpOnly, SameSite=Lax, Secure (base https), caminho restrito", "omni_oauth_nonce=" in cookie_hdr and "HttpOnly" in cookie_hdr
              and "samesite=lax" in cookie_hdr.lower() and "Secure" in cookie_hdr and "Path=/api/omni/oauth" in cookie_hdr)
        check("C5 o estado e assinado e vale 10 minutos", (lambda c: c["purpose"] == "ig_oauth" and 540 < c["exp"] - time.time() <= 601)(
            jwt.decode(qs["state"][0], settings.secret_key, algorithms=[settings.jwt_algorithm])))
        settings.omni_public_base_url = "http://api.test"  # o cliente de teste fala http: o cookie Secure so seria enviado em https
        eps_antes = count("select count(*) from tenant_endpoints")
        client.cookies.clear(); r, qs = connect(H)
        client.cookies.clear()
        check("C6 callback SEM o cookie e recusado (estado)", callback(code="GOODCODE", state=qs["state"][0]).headers["location"] == "/omni?ig_error=state")
        r, qs = connect(H)
        forged = jwt.encode({"purpose": "ig_oauth", "tid": str(demo.id), "uid": "x", "nonce": client.cookies.get("omni_oauth_nonce"), "exp": utcnow() + timedelta(minutes=5)}, "outra-chave", algorithm="HS256")
        check("C7 estado FALSIFICADO e recusado", callback(code="GOODCODE", state=forged).headers["location"] == "/omni?ig_error=state")
        expired = jwt.encode({"purpose": "ig_oauth", "tid": str(demo.id), "uid": "x", "nonce": "n", "exp": utcnow() - timedelta(minutes=1)}, settings.secret_key, algorithm=settings.jwt_algorithm)
        check("C8 estado EXPIRADO e recusado", callback(code="GOODCODE", state=expired).headers["location"] == "/omni?ig_error=state")
        check("C9 usuario cancela na Meta (access_denied)", callback(error="access_denied", state=qs["state"][0]).headers["location"] == "/omni?ig_error=denied")
        r, qs = connect(H)  # o cancelamento anterior apagou o cookie: novo fluxo
        check("C10 troca de codigo falha na Meta", callback(code="BADCODE", state=qs["state"][0]).headers["location"] == "/omni?ig_error=exchange")
        fake.permissions = "instagram_business_basic,instagram_business_manage_messages"
        r, qs = connect(H)
        check("C11 permissao faltando (sem comentarios) e recusada", callback(code="GOODCODE", state=qs["state"][0]).headers["location"] == "/omni?ig_error=permissions")
        fake.permissions = ",".join(meta_instagram.SCOPES); fake.me["account_type"] = "PERSONAL"
        r, qs = connect(H)
        check("C12 conta pessoal (nao profissional) e recusada", callback(code="GOODCODE", state=qs["state"][0]).headers["location"] == "/omni?ig_error=not_professional")
        fake.me["account_type"] = "BUSINESS"
        check("C13 nenhuma dessas tentativas gravou canal nem conexao", count("select count(*) from tenant_endpoints") == eps_antes and conexao(demo.id) is None)

        resp = full_connect(H)
        check("C14 fluxo correto: redireciona para /omni?ig=connected", resp.status_code == 303 and resp.headers["location"] == "/omni?ig=connected", resp.headers.get("location"))
        c = conexao(demo.id, IG_DEMO)
        check("C15 canal criado com o ID da conta profissional (o 'id' dos webhooks) e o @usuario", c and c["ig"] == IG_DEMO and c["usr"] == "mdpdemo")
        check("C16 conexao CONECTADO, webhook assinado, escopos gravados", c and c["status"] == "CONECTADO" and c["webhook_assinado"] and len(c["escopos"]) == 3)
        check("C17 token gravado CRIPTOGRAFADO (nao e o texto) e descriptografa para o token longo", c and "LONGTOKEN" not in c["token_enc"]
              and meta_crypto.decrypt_token(c["token_enc"]).startswith("LONGTOKEN"))
        check("C18 validade de ~60 dias e renovacao agendada antes do fim", c and 59 * 86400 < (c["token_expira_em"] - utcnow()).total_seconds() < 61 * 86400 and c["renovar_em"] < c["token_expira_em"])
        sub = fake.calls_to("/subscribed_apps")
        check("C19 webhooks assinados na Meta: messages e comments", len(sub) == 1 and sub[0]["params"]["subscribed_fields"] == "messages,comments" and f"/{IG_DEMO}/" in sub[0]["url"])
        integ = client.get("/api/omni/integrations", headers=H).json()
        ig = next(i for i in integ if i["provider"] == "INSTAGRAM")
        check("C20 tela: Instagram CONNECTED com nome e @usuario, sem expor segredos", ig["status"] == "CONNECTED" and ig["handle"] == "mdpdemo"
              and set(ig) == {"provider", "status", "account_name", "handle", "connected_at", "token_expires_at"})
        check("C21 o cookie do nonce e apagado ao voltar", "omni_oauth_nonce" in resp.headers.get("set-cookie", "") and "Max-Age=0" in resp.headers.get("set-cookie", ""))

        resp = full_connect(HA)  # outro tenant tenta a MESMA conta
        check("C22 a mesma conta em OUTRO tenant e recusada (already_connected)", resp.headers["location"] == "/omni?ig_error=already_connected")
        check("C23 e o tenant dono nao foi afetado", conexao(demo.id, IG_DEMO)["status"] == "CONECTADO")

        antes = conexao(demo.id, IG_DEMO)
        resp = full_connect(H)
        depois = conexao(demo.id, IG_DEMO)
        check("C24 reconectar a mesma conta atualiza o token sem duplicar canal", resp.headers["location"] == "/omni?ig=connected" and depois["ep"] == antes["ep"]
              and depois["token_enc"] != antes["token_enc"] and count("select count(*) from tenant_endpoints where tenant_id=:t and identificador_externo=:i", t=str(demo.id), i=IG_DEMO) == 1)

        fake.me = {"user_id": IG_MDP, "username": "teste.adocao.omni", "name": "Teste Adocao", "account_type": "Media_Creator"}
        resp = full_connect(HA)
        c2 = conexao(mdp.id, IG_MDP)
        check("C25 conta que casa com um cadastro manual ADOTA o canal existente (sem duplicar) e aceita conta 'Media_Creator'",
              resp.headers["location"] == "/omni?ig=connected" and c2 and str(c2["ep"]) == str(manual_ep)
              and count("select count(*) from tenant_endpoints where tenant_id=:t and tipo_endpoint_id=:p and ativo and lower(coalesce(identificador_publico,'')) = 'teste.adocao.omni'", t=str(mdp.id), p=str(tipo)) == 1)

        fake.me = {"user_id": IG_DEMO, "username": "mdpdemo", "name": "MDP Demo", "account_type": "BUSINESS"}
        sensivel = ("SHORTTOKEN-SECRET", "LONGTOKEN-", "GOODCODE", SECRET_IG, "REFRESHED-")
        check("C26 nenhum token, codigo ou segredo apareceu em LOG", not any(s in line for line in logcap.lines for s in sensivel))

        # ------------------------------------------------------------------ W. webhooks
        print("\n[W] Webhooks do Instagram")
        W = "/api/meta/instagram/webhook"
        check("W1 verificacao correta devolve o desafio", (lambda r: r.status_code == 200 and r.text == "12345")(client.get(W, params={"hub.mode": "subscribe", "hub.verify_token": VERIFY, "hub.challenge": "12345"})))
        check("W2 verificacao com token errado ou ausente = 403", client.get(W, params={"hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "1"}).status_code == 403
              and client.get(W, params={"hub.mode": "subscribe", "hub.challenge": "1"}).status_code == 403)
        cust = "17841400000000999"
        now_ms = int(time.time() * 1000)
        dm = lambda mid, **extra: {"object": "instagram", "entry": [{"id": IG_DEMO, "time": now_ms, "messaging": [
            {"sender": {"id": extra.get("sender", cust)}, "recipient": {"id": IG_DEMO}, "timestamp": now_ms, "message": {"mid": mid, **extra.get("msg", {"text": "Hi! Do you have availability this week?"})}}]}]}
        raw, hdr = signed(dm("mid.IN1"), "segredo-errado")
        check("W3 assinatura invalida = 403 e nada gravado", client.post(W, content=raw, headers=hdr).status_code == 403 and count("select 1 from information_schema.tables limit 1") == 1)
        with tenant_session(db, demo.id) as t:
            base_msgs = t.execute(text("select count(*) from omni_mensagens")).scalar()
        raw, hdr = signed(dm("mid.IN1"))
        r = client.post(W, content=raw, headers=hdr)
        check("W4 DM com assinatura valida = 200", r.status_code == 200 and r.json() == {"received": True})
        convs = client.get("/api/omni/conversations", headers=H).json()
        conv = next((c for c in convs if c["last_text"] and "availability" in c["last_text"]), None)
        check("W5 conversa criada, com nome e @usuario buscados no perfil, janela de 24h aberta e 1 nao lida",
              conv and conv["name"] == "Cliente Teste" and conv["username"] == "cliente.teste" and conv["reply_window_open"] and conv["unread"] == 1)
        client.post(W, content=raw, headers=hdr)
        msgs = client.get(f"/api/omni/conversations/{conv['id']}/messages", headers=H).json()["messages"]
        check("W6 o mesmo evento reenviado nao duplica (idempotente)", len([m for m in msgs if m["text"] and "availability" in m["text"]]) == 1)
        n_calls = len(fake.calls)
        for payload in (dm("mid.ECHO1", sender=IG_DEMO), dm("mid.ECHO2", msg={"text": "eco", "is_echo": True}), dm("mid.SELF1", msg={"text": "self", "is_self": True}),
                        dm("mid.DEL1", msg={"is_deleted": True})):
            r_, h_ = signed(payload); client.post(W, content=r_, headers=h_)
        msgs = client.get(f"/api/omni/conversations/{conv['id']}/messages", headers=H).json()["messages"]
        check("W7 ecos, auto-mensagens e apagadas sao ignorados", len(msgs) == 1 and not any(c["name"] is None and c["last_text"] in ("eco", "self") for c in client.get("/api/omni/conversations", headers=H).json()))
        r_, h_ = signed({"object": "instagram", "entry": [{"id": "99999999", "time": 1, "messaging": [{"sender": {"id": "5"}, "recipient": {"id": "99999999"}, "timestamp": now_ms, "message": {"mid": "mid.X", "text": "oi"}}]}]})
        check("W8 conta desconhecida: 200 e nada gravado", client.post(W, content=r_, headers=h_).status_code == 200)
        r_, h_ = signed(dm("mid.ALT1", msg={"text": "alt secret"}), SECRET_MAIN)
        check("W9 assinatura feita com o segredo do app principal tambem e aceita", client.post(W, content=r_, headers=h_).status_code == 200
              and any(m["text"] == "alt secret" for m in client.get(f"/api/omni/conversations/{conv['id']}/messages", headers=H).json()["messages"]))
        r_, h_ = signed([dm("mid.LIST1", msg={"text": "formato em lista"})])
        client.post(W, content=r_, headers=h_)
        check("W10 payload embrulhado em lista (como na documentacao) tambem funciona", any(m["text"] == "formato em lista" for m in client.get(f"/api/omni/conversations/{conv['id']}/messages", headers=H).json()["messages"]))
        r_, h_ = signed(dm("mid.ATT1", msg={"attachments": [{"type": "image", "payload": {"url": "https://x/y.png"}}]}))
        client.post(W, content=r_, headers=h_)
        check("W11 anexo vira '[attachment]' (sem guardar a URL)", any(m["text"] == "[attachment]" for m in client.get(f"/api/omni/conversations/{conv['id']}/messages", headers=H).json()["messages"]))
        big = b"x" * 1_000_001
        check("W12 corpo gigante = 413", client.post(W, content=big, headers={"x-hub-signature-256": "sha256=0", "content-type": "application/json"}).status_code == 413)

        cm = lambda cid, **v: {"object": "instagram", "entry": [{"id": IG_DEMO, "time": now_ms, "changes": [{"field": "comments", "value": {
            "id": cid, "from": v.get("frm", {"id": "555", "username": "carla.mendes"}), "text": v.get("text", "Does this include weekends?"), "media": {"id": "M1", "media_product_type": "FEED"}}}]}]}
        r_, h_ = signed(cm("C100")); client.post(W, content=r_, headers=h_)
        comments = client.get("/api/omni/comments", headers=H).json()
        carla = next((c for c in comments if c["text"] == "Does this include weekends?"), None)
        check("W13 comentario gravado com o post de origem (legenda buscada na Meta)", carla and carla["author_username"] == "carla.mendes" and carla["post"] == "Spring promotion, book this week" and carla["post_url"])
        for payload in (cm("C101", frm={"id": IG_DEMO, "username": "outro"}), cm("C102", frm={"id": "777", "username": "mdpdemo"})):
            r_, h_ = signed(payload); client.post(W, content=r_, headers=h_)
        check("W14 comentarios da PROPRIA conta (por ID ou por @usuario) sao ignorados", len(client.get("/api/omni/comments", headers=H).json()) == len(comments))
        r_, h_ = signed({"object": "instagram", "entry": [{"id": IG_DEMO, "time": now_ms, "field": "comments", "value": {"id": "C103", "from": {"id": "9", "username": "ana.costa"}, "text": "formato direto", "media": {"id": "M1"}}}]})
        client.post(W, content=r_, headers=h_)
        check("W15 formato com field/value direto no entry tambem e aceito", any(c["text"] == "formato direto" for c in client.get("/api/omni/comments", headers=H).json()))

        from sqlalchemy.exc import SQLAlchemyError
        original = omni_store.store_incoming_dm
        omni_store.store_incoming_dm = lambda *a, **k: (_ for _ in ()).throw(SQLAlchemyError("falha simulada"))
        r_, h_ = signed(dm("mid.RETRY1", msg={"text": "vai tentar de novo"}))
        falha = client.post(W, content=r_, headers=h_).status_code
        omni_store.store_incoming_dm = original
        check("W16 falha de banco = 500 (a Meta reenvia) e o reenvio grava normalmente", falha == 500 and client.post(W, content=r_, headers=h_).status_code == 200
              and any(m["text"] == "vai tentar de novo" for m in client.get(f"/api/omni/conversations/{conv['id']}/messages", headers=H).json()["messages"]))

        # ------------------------------------------------------------------ S. envio
        print("\n[S] Responder pelo Omni")
        fake.calls.clear()
        r = client.post(f"/api/omni/conversations/{conv['id']}/reply", json={"text": "Yes! Thursday at 10."}, headers=H)
        call = (fake.calls_to("/messages") or [{}])[0]
        check("S1 DM enviada: 201 e ENVIADA com o ID da Meta", r.status_code == 201 and r.json()["status"] == "ENVIADA" and r.json()["error"] is None)
        check("S2 chamada correta: /<IG_ID>/messages, Bearer, destinatario e texto", f"/{IG_DEMO}/messages" in call.get("url", "") and call["headers"].get("Authorization", "").startswith("Bearer LONGTOKEN")
              and call["json"] == {"recipient": {"id": cust}, "message": {"text": "Yes! Thursday at 10."}})
        fake.fail["/messages"] = meta_instagram.MetaApiError(400, "190", "token expirado")
        r = client.post(f"/api/omni/conversations/{conv['id']}/reply", json={"text": "outra"}, headers=H)
        check("S3 erro da Meta (token expirado, 190): FALHA com codigo curto e seguro", r.status_code == 201 and r.json()["status"] == "FALHA" and r.json()["error"] == "meta_190")
        fake.fail["/messages"] = meta_instagram.MetaApiError(0, "network", "ConnectError")
        r = client.post(f"/api/omni/conversations/{conv['id']}/reply", json={"text": "outra 2"}, headers=H)
        check("S4 Meta fora do ar: FALHA 'meta_unavailable' (nunca 500)", r.status_code == 201 and r.json()["error"] == "meta_unavailable")
        fake.fail.clear()
        check("S5 texto acima de 1000 BYTES (emojis) = 422, antes de chamar a Meta", client.post(f"/api/omni/conversations/{conv['id']}/reply", json={"text": "😀" * 300}, headers=H).status_code == 422)
        fake.calls.clear()
        r = client.post(f"/api/omni/comments/{carla['id']}/reply", json={"text": "Yes, weekends too."}, headers=H)
        call = (fake.calls_to("/replies") or [{}])[0]
        check("S6 resposta a comentario: 201 ENVIADA, chamada /<comentario>/replies com a mensagem", r.status_code == 201 and r.json()["status"] == "ENVIADA" and "/C100/replies" in call.get("url", "")
              and call["json"] == {"message": "Yes, weekends too."})
        carla2 = next(c for c in client.get("/api/omni/comments", headers=H).json() if c["id"] == carla["id"])
        check("S7 o comentario passa a 'respondido' e mostra a resposta", carla2["replied"] is True and len(carla2["replies"]) == 1)
        fake.fail["/replies"] = meta_instagram.MetaApiError(400, "100", "erro")
        ana = next(c for c in client.get("/api/omni/comments", headers=H).json() if c["text"] == "formato direto")
        r = client.post(f"/api/omni/comments/{ana['id']}/reply", json={"text": "falha"}, headers=H)
        ana2 = next(c for c in client.get("/api/omni/comments", headers=H).json() if c["id"] == ana["id"])
        check("S8 falha ao responder comentario: FALHA e o comentario NAO vira 'respondido'", r.json()["status"] == "FALHA" and ana2["replied"] is False)
        fake.fail.clear()

        # ------------------------------------------------------------------ Y. sincronizacao de comentarios
        print("\n[Y] Comentarios por consulta (funciona com Acesso Padrao)")
        fake.comments["M1"] = [{"id": "C200", "text": "Where is the price list?", "username": "ana.costa", "timestamp": "2026-10-07T12:00:00+0000"},
                               {"id": "C100", "text": "Does this include weekends?", "username": "carla.mendes", "timestamp": "2026-10-07T11:00:00+0000"},
                               {"id": "C201", "text": "minha propria resposta", "username": "mdpdemo", "timestamp": "2026-10-07T12:05:00+0000"}]
        r = client.post("/api/omni/comments/sync", headers=H)
        check("Y1 sync grava so os comentarios novos (nao repete o ja recebido por webhook nem os da propria conta)", r.json() == {"new": 1, "skipped": False}, str(r.json()))
        check("Y2 o comentario novo aparece na lista com o post de origem", any(c["text"] == "Where is the price list?" and c["post"] == "Spring promotion, book this week" for c in client.get("/api/omni/comments", headers=H).json()))
        n_calls = len(fake.calls)
        check("Y3 segunda sincronizacao em seguida e adiada (nao chama a Meta)", client.post("/api/omni/comments/sync", headers=H).json() == {"new": 0, "skipped": True} and len(fake.calls) == n_calls)
        db.execute(text("update canal_conexoes set metadados = metadados - 'last_comment_sync' where tenant_id=:t"), {"t": str(demo.id)}); db.commit()
        check("Y4 passado o intervalo, repetir nao duplica nada", client.post("/api/omni/comments/sync", headers=H).json() == {"new": 0, "skipped": False})
        db.execute(text("update canal_conexoes set metadados = metadados - 'last_comment_sync' where tenant_id=:t"), {"t": str(demo.id)}); db.commit()
        fake.fail["/media"] = meta_instagram.MetaApiError(400, "190", "x")
        r = client.post("/api/omni/comments/sync", headers=H)
        check("Y5 erro da Meta na sincronizacao nao derruba a tela (devolve o codigo)", r.status_code == 200 and r.json().get("error") == "190")
        fake.fail.clear()

        # ------------------------------------------------------------------ R. renovacao
        print("\n[R] Renovacao automatica do token")
        db.execute(text("update canal_conexoes set renovar_em = now() - interval '1 hour' where tenant_id=:t"), {"t": str(demo.id)}); db.commit()
        antes = conexao(demo.id, IG_DEMO)["token_enc"]
        stats = omni_refresh_tokens.run()
        dep = conexao(demo.id, IG_DEMO)
        check("R1 token perto de vencer e renovado (novo token, nova validade, nova data de renovacao)", stats["renovados"] >= 1 and dep["token_enc"] != antes
              and meta_crypto.decrypt_token(dep["token_enc"]).startswith("REFRESHED") and dep["renovar_em"] > utcnow() and dep["status"] == "CONECTADO")
        db.execute(text("update canal_conexoes set renovar_em = now() - interval '1 hour' where tenant_id=:t"), {"t": str(demo.id)}); db.commit()
        fake.fail["/refresh_access_token"] = meta_instagram.MetaApiError(400, "190", "token invalido")
        stats = omni_refresh_tokens.run()
        dep = conexao(demo.id, IG_DEMO)
        check("R2 token invalido na renovacao: marca EXPIRADO e registra o erro, sem quebrar", stats["expirados"] >= 1 and dep["ultimo_erro"] == "refresh:190")
        fake.fail.clear()
        ig = next(i for i in client.get("/api/omni/integrations", headers=H).json() if i["provider"] == "INSTAGRAM")
        check("R3 a tela passa a mostrar EXPIRED", ig["status"] == "EXPIRED")
        full_connect(H)  # reconectar corrige
        ig = next(i for i in client.get("/api/omni/integrations", headers=H).json() if i["provider"] == "INSTAGRAM")
        check("R4 reconectar volta para CONNECTED e limpa o erro", ig["status"] == "CONNECTED" and conexao(demo.id, IG_DEMO)["ultimo_erro"] is None)

        # ------------------------------------------------------------------ D. desconectar
        print("\n[D] Desconectar")
        r = client.delete("/api/omni/integrations/INSTAGRAM", headers=H)
        c = conexao(demo.id, IG_DEMO)
        check("D1 desconectar: REVOGADO, token APAGADO, webhook desmarcado", r.json() == {"disconnected": True} and c["status"] == "REVOGADO" and c["token_enc"] is None and not c["webhook_assinado"])
        ig = next(i for i in client.get("/api/omni/integrations", headers=H).json() if i["provider"] == "INSTAGRAM")
        check("D2 a tela mostra REVOKED", ig["status"] == "REVOKED")
        r_, h_ = signed(dm("mid.AFTER1", msg={"text": "depois de desconectar"}))
        check("D3 eventos de conta desconectada sao ignorados (200, nada gravado)", client.post(W, content=r_, headers=h_).status_code == 200
              and not any(m["text"] == "depois de desconectar" for m in client.get(f"/api/omni/conversations/{conv['id']}/messages", headers=H).json()["messages"]))
        r = client.post(f"/api/omni/conversations/{conv['id']}/reply", json={"text": "apos desconectar"}, headers=H)
        check("D4 responder apos desconectar: FALHA 'channel_not_connected'", r.json()["status"] == "FALHA" and r.json()["error"] == "channel_not_connected")
        check("D5 desconectar de novo e inofensivo", client.delete("/api/omni/integrations/INSTAGRAM", headers=H).json() == {"disconnected": False})
        check("D6 FACEBOOK segue 501 (ainda nao conectado)", client.post("/api/omni/integrations/FACEBOOK/connect", headers=H).status_code == 501)
        resp = full_connect(H)
        check("D7 e possivel conectar de novo depois de desconectar", resp.headers["location"] == "/omni?ig=connected" and conexao(demo.id, IG_DEMO)["status"] == "CONECTADO")

        # ------------------------------------------------------------------ L. logs
        print("\n[L] Segredos fora dos logs")
        from app import logging_filters
        rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                                ("1.2.3.4:5", "GET", "/api/omni/oauth/instagram/callback?code=ABC123&state=eyJ.x.y", "1.1", 303), None)
        logging_filters.RedactSecretsFilter().filter(rec)
        line = rec.getMessage()
        check("L1 o log de acesso mascara o codigo OAuth e o estado", "ABC123" not in line and "eyJ.x.y" not in line and "code=REDACTED" in line and "state=REDACTED" in line)
        rec = logging.LogRecord("httpx", logging.INFO, "", 0, 'HTTP Request: GET https://graph.instagram.com/v25.0/me?fields=a&access_token=SECRETTOKEN "HTTP/1.1 200 OK"', None, None)
        logging_filters.RedactSecretsFilter().filter(rec)
        check("L2 o log do cliente HTTP mascara access_token", "SECRETTOKEN" not in rec.getMessage())
        check("L3 o cliente HTTP so registra a partir de WARNING (nao grava URLs de chamadas)", logging.getLogger("httpx").level == logging.WARNING)
        # a Meta manda o token de verificacao com PONTO e com SUBLINHADO na mesma chamada (visto em producao): as duas grafias
        rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d', ("10.0.1.4:1", "GET",
                                "/api/meta/instagram/webhook?hub.mode=subscribe&hub.challenge=968607311&hub.verify_token=SEGREDO-PONTO&hub_mode=subscribe&hub_challenge=968607311&hub_verify_token=SEGREDO-SUBLINHADO",
                                "1.1", 200), None)
        logging_filters.RedactSecretsFilter().filter(rec)
        line = rec.getMessage()
        check("L4 o token de verificacao e mascarado nas DUAS grafias (hub.verify_token e hub_verify_token), sem apagar o desafio",
              "SEGREDO-PONTO" not in line and "SEGREDO-SUBLINHADO" not in line and "hub.challenge=968607311" in line)
        rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d', ("10.0.1.4:1", "POST",
                                "/api/auth/mfa/setup?preauth_token=eyJhbGciOi.PREAUTH.x&refresh_token=REFRESH-X&client_secret=CS", "1.1", 200), None)
        logging_filters.RedactSecretsFilter().filter(rec)
        line = rec.getMessage()
        check("L5 preauth_token do MFA, refresh_token e client_secret tambem sao mascarados", all(x not in line for x in ("PREAUTH", "REFRESH-X", "CS\"")) and "preauth_token=REDACTED" in line)
        rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d', ("10.0.1.4:1", "GET", "/api/omni/conversations?channel=INSTAGRAM&limit=20", "1.1", 200), None)
        logging_filters.RedactSecretsFilter().filter(rec)
        check("L6 parametros comuns (canal, limite) NAO sao mascarados", "channel=INSTAGRAM&limit=20" in rec.getMessage())

        # ------------------------------------------------------------------ X. permissao
        print("\n[X] Permissoes")
        check("X1 sem login: connect, sync e desconectar sao recusados", all(code in (401, 403) for code in (
            client.post("/api/omni/integrations/INSTAGRAM/connect").status_code, client.post("/api/omni/comments/sync").status_code,
            client.delete("/api/omni/integrations/INSTAGRAM").status_code)))
        check("X2 o callback sem estado nunca conecta nada", callback(code="GOODCODE").headers["location"] == "/omni?ig_error=state")
        settings.omni_meta_enabled = False
        check("X3 ao desligar a chave, o webhook volta a 404 e o connect a 501", client.get(W).status_code == 404 and client.post("/api/omni/integrations/INSTAGRAM/connect", headers=H).status_code == 501)
        settings.omni_meta_enabled = True
        check("X4 nenhuma resposta da API contem token", "LONGTOKEN" not in json.dumps(client.get("/api/omni/integrations", headers=H).json()))
        check("X5 ao final, nenhum token, codigo ou segredo apareceu em LOG", not any(s in line for line in logcap.lines for s in sensivel))
    finally:
        logging.getLogger().removeHandler(logcap)
        db.rollback()
        created = [r[0] for r in db.execute(text("select id from tenant_endpoints")) if str(r[0]) not in baseline_eps]
        ids = [str(i) for i in created] + ([str(manual_ep)] if manual_ep else [])
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
