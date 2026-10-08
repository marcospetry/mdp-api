"""
Teste automatico dos callbacks de privacidade da Meta (desautorizacao e exclusao de dados) e da pagina de status,
com uma META SIMULADA (nenhuma chamada real sai daqui) e pedidos assinados gerados aqui mesmo.

ONDE RODAR: SOMENTE em banco de TESTE/DEV (trava por APP_ENV). Cria e REMOVE um usuario, canais, pedidos e dados de teste nos
tenants MDP e MDP_DEMO. Nao imprime tokens, codigos do OAuth nem segredos.

Uso:  python scripts/test_omni_privacy.py
Pre-requisitos: migrations platform 010 e 011 e tenant 006 aplicadas; tenants MDP e MDP_DEMO provisionados.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import jwt
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import settings
from app.database import PlatformSessionLocal, tenant_session
from app.main import app
from app.services import meta_instagram, meta_privacy, omni_store
from app.services.auth_service import utcnow

SECRET_IG, SECRET_MAIN = "ig-secret-for-tests", "main-secret-for-tests"
IG_ID, APP_UID, UNKNOWN_UID = "17841400000000777", "appscoped777", "999000999000"
EMAIL = "privacy.test@exemplo-teste.com.br"
resultados: list[bool] = []
client = TestClient(app)


def check(nome, cond, detalhe=""):
    resultados.append(bool(cond))
    print(("  OK   " if cond else "  FALHA") + f"  {nome}" + (f"  [{detalhe}]" if detalhe and not cond else ""))


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def signed_request(payload: dict, secret: str = SECRET_IG) -> str:
    part = b64(json.dumps(payload).encode())
    sig = b64(hmac.new(secret.encode(), part.encode(), hashlib.sha256).digest())
    return f"{sig}.{part}"


def post_form(path: str, sr: str | None, raw: bytes | None = None):
    body = raw if raw is not None else urlencode({"signed_request": sr or ""}).encode()
    return client.post(path, content=body, headers={"content-type": "application/x-www-form-urlencoded"})


def post_multipart(path: str, sr: str):
    boundary = "------------------------DoXLPL"
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="signed_request"\r\n\r\n{sr}\r\n--{boundary}--\r\n').encode()
    return client.post(path, content=body, headers={"content-type": f"multipart/form-data; boundary={boundary}"})


def payload_for(uid: str) -> dict:
    return {"algorithm": "HMAC-SHA256", "issued_at": int(time.time()), "user_id": uid}


class LogCapture(logging.Handler):
    def __init__(self):
        super().__init__(); self.lines: list[str] = []
    def emit(self, record):
        self.lines.append(record.getMessage())


class FakeMeta:
    """Responde so o que o Connect usa; qualquer outra chamada e erro de teste."""
    def __call__(self, method, url, *, params=None, data=None, json_body=None, headers=None, timeout=15.0):
        path = urlparse(url).path
        if url == meta_instagram.OAUTH_TOKEN:
            return {"data": [{"access_token": "SHORTTOKEN-SECRET", "user_id": APP_UID, "permissions": ",".join(meta_instagram.SCOPES)}]}
        if path.endswith("/access_token"):
            return {"access_token": "LONGTOKEN-SECRET", "token_type": "bearer", "expires_in": 5183944}
        if path.endswith("/me"):
            return {"data": [{"user_id": IG_ID, "username": "privacy.test", "name": "Privacy Test", "account_type": "BUSINESS"}]}
        if path.endswith("/subscribed_apps"):
            return {"success": True}
        raise AssertionError(f"chamada inesperada a Meta: {method} {path}")


def exigir_ambiente_de_teste():
    if settings.app_env.strip().lower() not in ("development", "dev", "test", "local"):
        sys.exit("Recusado: APP_ENV='%s'. So pode rodar em DEV/teste." % settings.app_env)


def main():
    exigir_ambiente_de_teste()
    meta_instagram.http_json = FakeMeta()
    saved = {k: getattr(settings, k) for k in ("omni_meta_enabled", "omni_public_base_url", "omni_connection_encryption_key",
                                                 "instagram_app_id", "instagram_app_secret", "instagram_webhook_verify_token",
                                                 "meta_whatsapp_app_secret")}
    settings.omni_meta_enabled = False  # os callbacks NAO dependem da chave (so o Connect, ligado so no bloco D)
    settings.omni_public_base_url = "https://api.test"
    settings.omni_connection_encryption_key = Fernet.generate_key().decode()
    settings.instagram_app_id, settings.instagram_app_secret = "1043605645256145", SECRET_IG
    settings.instagram_webhook_verify_token, settings.meta_whatsapp_app_secret = "verify-for-tests", SECRET_MAIN

    db = PlatformSessionLocal()
    tenants = {r[0]: r[1] for r in db.execute(text("select codigo, id from tenants"))}
    mdp, demo = tenants["MDP"], tenants["MDP_DEMO"]
    logcap = LogCapture(); logging.getLogger().addHandler(logcap); logging.getLogger().setLevel(logging.INFO)
    user_id = None
    endpoints: list[str] = []
    ids_testados = (APP_UID, IG_ID, UNKNOWN_UID)

    def q(sql, **p):
        db.expire_all()
        return db.execute(text(sql), p).mappings().all()

    def conexao():
        rows = q("""select c.status, c.token_enc, c.webhook_assinado, c.metadados, e.id as ep, e.ativo, e.nome,
                           e.identificador_externo as ig, e.identificador_publico as usr
                      from canal_conexoes c join tenant_endpoints e on e.id = c.endpoint_id
                     where e.tenant_id = :t and e.codigo like 'INSTAGRAM_PRIVACY_TEST%' order by e.created_at desc""", t=str(demo))
        return rows[0] if rows else None

    def pedidos(tipo=None):
        return q("""select codigo, tipo, status, canais_afetados from meta_pedidos_privacidade
                     where meta_user_id = any(:ids) and (CAST(:tipo AS text) is null or tipo = :tipo) order by created_at""",
                 ids=list(ids_testados), tipo=tipo)

    def seed_data(ep: str) -> None:
        with tenant_session(db, demo) as t:
            r1 = omni_store.store_incoming_dm(t, endpoint_id=ep, sender_id="cliente-1", mid="mid.priv.1", body="Hello, do you open on Sunday?",
                                              tipo="TEXTO", ts=omni_store.to_datetime(int(time.time())))
            omni_store.store_incoming_dm(t, endpoint_id=ep, sender_id="cliente-1", mid="mid.priv.2", body="Second private message",
                                         tipo="TEXTO", ts=omni_store.to_datetime(int(time.time())))
            omni_store.store_comment(t, endpoint_id=ep, comment_id="c.priv.1", media_id="m.1", parent_id=None, body="Nice post, private comment",
                                     author_id="cliente-1", author_username="cliente.priv", ts=omni_store.to_datetime(int(time.time())))

    def tenant_counts(tenant_id, ep: str) -> tuple[int, int, int]:
        with tenant_session(db, tenant_id) as t:
            c = t.execute(text("select count(*) from omni_conversas where endpoint_id = :e"), {"e": ep}).scalar()
            m = t.execute(text("""select count(*) from omni_mensagens x join omni_conversas c on c.id = x.conversa_id where c.endpoint_id = :e"""), {"e": ep}).scalar()
            k = t.execute(text("select count(*) from omni_comentarios where endpoint_id = :e"), {"e": ep}).scalar()
        return c, m, k

    def connect_demo() -> str:
        """Conecta o IG de teste ao tenant Demo pelo callback real do OAuth (state assinado + nonce)."""
        settings.omni_meta_enabled = True
        try:
            nonce = "nonce-privacy-test"
            state = jwt.encode({"purpose": "ig_oauth", "tid": str(demo), "uid": str(user_id), "nonce": nonce,
                                "exp": utcnow() + __import__("datetime").timedelta(seconds=300)},
                               settings.secret_key, algorithm=settings.jwt_algorithm)
            r = client.get("/api/omni/oauth/instagram/callback", params={"code": "GOODCODE", "state": state},
                           headers={"cookie": f"omni_oauth_nonce={nonce}"}, follow_redirects=False)
            assert r.status_code == 303 and "ig=connected" in r.headers["location"], r.headers.get("location")
        finally:
            settings.omni_meta_enabled = False
        ep = str(conexao()["ep"])
        endpoints.append(ep)
        return ep

    try:
        # ------------------------------------------------------------------ fixtures
        print("\n[0] Fixtures")
        db.execute(text("delete from usuarios where email = :e"), {"e": EMAIL}); db.commit()
        user_id = db.execute(text("""insert into usuarios (nome, email, password_hash) values ('Privacy Test', :e, 'x') returning id"""), {"e": EMAIL}).scalar()
        db.commit()
        check("0.1 usuario de teste criado", user_id is not None)
        check("0.2 tabela de pedidos existe (migration 011)",
              db.execute(text("select to_regclass('public.meta_pedidos_privacidade')")).scalar() is not None)

        # ------------------------------------------------------------------ A. signed_request (unidade)
        print("\n[A] signed_request")
        S = [SECRET_IG, SECRET_MAIN]
        ok = meta_privacy.parse_signed_request(signed_request(payload_for(APP_UID)), S)
        check("A1 assinatura valida (segredo do Instagram)", ok and ok["user_id"] == APP_UID)
        check("A2 assinatura valida (segredo do app principal)",
              meta_privacy.parse_signed_request(signed_request(payload_for(APP_UID), SECRET_MAIN), S) is not None)
        check("A3 segredo errado e recusado", meta_privacy.parse_signed_request(signed_request(payload_for(APP_UID), "outro-segredo"), S) is None)
        good = signed_request(payload_for(APP_UID))
        sig, part = good.split(".")
        adulterado = sig + "." + b64(json.dumps(payload_for("outro-usuario")).encode())
        check("A4 payload adulterado e recusado", meta_privacy.parse_signed_request(adulterado, S) is None)
        check("A5 sem ponto / vazio / None", all(meta_privacy.parse_signed_request(v, S) is None for v in ("semponto", "", None, "a.b.c")))
        check("A6 base64 invalido e JSON invalido", meta_privacy.parse_signed_request("@@@.@@@", S) is None
              and meta_privacy.parse_signed_request(b64(b"x") + "." + b64(b"nao-json"), S) is None)
        check("A7 algoritmo diferente de HMAC-SHA256 e recusado",
              meta_privacy.parse_signed_request(signed_request({**payload_for(APP_UID), "algorithm": "none"}), S) is None)
        check("A8 sem user_id ou user_id vazio e recusado",
              meta_privacy.parse_signed_request(signed_request({"algorithm": "HMAC-SHA256"}), S) is None
              and meta_privacy.parse_signed_request(signed_request({"algorithm": "HMAC-SHA256", "user_id": "  "}), S) is None)
        check("A9 sem nenhum segredo configurado nada passa", meta_privacy.parse_signed_request(good, []) is None)
        check("A10 extract_signed_request le o campo do formulario",
              meta_privacy.extract_signed_request(b"signed_request=abc.def&x=1") == "abc.def"
              and meta_privacy.extract_signed_request(b"x=1") is None and meta_privacy.extract_signed_request(b"\xff\xfe") is None)
        mp = b'--XX\r\nContent-Disposition: form-data; name="signed_request"\r\n\r\nabc.def\r\n--XX--\r\n'
        mp_ct = "multipart/form-data; boundary=XX"
        check("A11 extract_signed_request le multipart/form-data (formato real do deauthorize)",
              meta_privacy.extract_signed_request(mp, mp_ct) == "abc.def"
              and meta_privacy.extract_signed_request(mp.replace(b"signed_request", b"outro"), mp_ct) is None
              and meta_privacy.extract_signed_request(b"lixo", mp_ct) is None)

        # ------------------------------------------------------------------ B/C. protecao das rotas
        print("\n[B/C] Protecao das rotas")
        for path in ("/api/meta/deauthorize", "/api/meta/data-deletion"):
            r = post_form(path, signed_request(payload_for(APP_UID), "outro-segredo"))
            check(f"B1 {path}: assinatura invalida -> 403", r.status_code == 403, r.status_code)
            check(f"B2 {path}: corpo sem signed_request -> 403", post_form(path, None, raw=b"foo=bar").status_code == 403)
            check(f"B3 {path}: corpo gigante -> 413", post_form(path, None, raw=b"signed_request=" + b"a" * 30_000).status_code == 413)
        n_antes = len(pedidos())
        saved_ig, saved_main = settings.instagram_app_secret, settings.meta_whatsapp_app_secret
        settings.instagram_app_secret, settings.meta_whatsapp_app_secret = None, "change-me"
        r = post_form("/api/meta/data-deletion", signed_request(payload_for(APP_UID)))
        settings.instagram_app_secret, settings.meta_whatsapp_app_secret = saved_ig, saved_main
        check("B4 sem nenhum segredo configurado -> 404", r.status_code == 404, r.status_code)
        check("B5 pedidos recusados nao gravam nada", len(pedidos()) == n_antes)
        check("B6 os callbacks respondem com OMNI_META_ENABLED desligado", settings.omni_meta_enabled is False)

        print("\n[C2] Diagnostico da recusa no log")
        n0 = len(logcap.lines)
        sr_errado = signed_request(payload_for(APP_UID), "outro-segredo")
        post_form("/api/meta/deauthorize", sr_errado)
        post_form("/api/meta/data-deletion", None, raw=b"foo=bar")
        post_form("/api/meta/deauthorize", "semponto")
        post_form("/api/meta/deauthorize", signed_request({**payload_for(APP_UID), "algorithm": "HMAC-SHA1"}))
        novas = "\n".join(logcap.lines[n0:])
        check("C2.1 assinatura errada: motivo=assinatura com nomes de campos e rota", "motivo=assinatura" in novas and "chaves=['algorithm', 'issued_at', 'user_id']" in novas and "rota=deauthorize" in novas, novas[:200])
        check("C2.2 sem signed_request: motivo=sem_campo (rota data-deletion)", "motivo=sem_campo" in novas and "rota=data-deletion" in novas)
        check("C2.3 formato invalido: motivo=formato", "motivo=formato" in novas)
        check("C2.4 algoritmo diferente: motivo=algoritmo", "motivo=algoritmo" in novas)
        check("C2.5 o log nao traz o signed_request, o user_id nem segredos", sr_errado not in novas and APP_UID not in novas and "outro-segredo" not in novas and SECRET_IG not in novas)
        check("C2.6 diagnose nao aceita nada que parse recusa",
              meta_privacy.diagnose_signed_request(signed_request(payload_for(APP_UID)), S)["motivo"] == "ok"
              and meta_privacy.diagnose_signed_request(sr_errado, S)["motivo"] == "assinatura")

        # ------------------------------------------------------------------ D. Connect grava o ID do usuario no app
        print("\n[D] Connect grava app_user_id")
        ep1 = connect_demo()
        c = conexao()
        check("D1 conexao CONECTADO", c["status"] == "CONECTADO" and c["token_enc"] is not None)
        check("D2 metadados.app_user_id = user_id da troca do codigo", (c["metadados"] or {}).get("app_user_id") == APP_UID)
        check("D3 identificador_externo continua sendo o ID do /me (webhook)", c["ig"] == IG_ID)
        seed_data(ep1)
        check("D4 dados de teste gravados no tenant Demo", tenant_counts(demo, ep1) == (1, 2, 1), tenant_counts(demo, ep1))
        # dado de OUTRO tenant (MDP) para provar isolamento da exclusao
        ep_outro = db.execute(text("""insert into tenant_endpoints (tenant_id, codigo, nome, identificador_externo, tipo_endpoint_id)
                                      values (:t, 'INSTAGRAM_PRIVACY_TEST_OUTRO', 'Outro', '17841400000000888',
                                              (select id from tipos_endpoint where codigo='INSTAGRAM')) returning id"""), {"t": str(mdp)}).scalar()
        db.commit(); endpoints.append(str(ep_outro))
        with tenant_session(db, mdp) as t:
            omni_store.store_incoming_dm(t, endpoint_id=ep_outro, sender_id="x", mid="mid.outro", body="outro tenant", tipo="TEXTO",
                                         ts=omni_store.to_datetime(int(time.time())))

        # ------------------------------------------------------------------ E. desautorizacao
        print("\n[E] Desautorizacao")
        r = post_form("/api/meta/deauthorize", signed_request(payload_for(APP_UID)))
        check("E1 200 {received: true}", r.status_code == 200 and r.json() == {"received": True}, r.text)
        c = conexao()
        check("E2 conexao REVOGADO, token apagado, webhook desligado",
              c["status"] == "REVOGADO" and c["token_enc"] is None and c["webhook_assinado"] is False)
        check("E3 o conteudo NAO e apagado na desautorizacao", tenant_counts(demo, ep1) == (1, 2, 1))
        p = pedidos("DESAUTORIZACAO")
        check("E4 pedido registrado como CONCLUIDO com 1 canal", len(p) == 1 and p[0]["status"] == "CONCLUIDO" and p[0]["canais_afetados"] == 1, [dict(x) for x in p])
        r2 = post_form("/api/meta/deauthorize", signed_request(payload_for(APP_UID)))
        check("E5 repetir o pedido e inofensivo (200)", r2.status_code == 200)
        r3 = post_form("/api/meta/deauthorize", signed_request(payload_for(UNKNOWN_UID)))
        p3 = [x for x in pedidos("DESAUTORIZACAO") if x["status"] == "SEM_CORRESPONDENCIA"]
        check("E6 usuario desconhecido: 200 e registro SEM_CORRESPONDENCIA", r3.status_code == 200 and len(p3) == 1)
        # a Meta ja enviou o deauthorize como multipart/form-data (log real): precisa ser aceito
        r4 = post_multipart("/api/meta/deauthorize", signed_request(payload_for(APP_UID)))
        check("E7 multipart/form-data valido -> 200", r4.status_code == 200 and r4.json() == {"received": True}, r4.text)
        r5 = post_multipart("/api/meta/deauthorize", signed_request(payload_for(APP_UID), "outro-segredo"))
        check("E8 multipart com assinatura invalida -> 403", r5.status_code == 403, r5.status_code)

        # ------------------------------------------------------------------ F. exclusao de dados
        print("\n[F] Exclusao de dados")
        r = post_form("/api/meta/data-deletion", signed_request(payload_for(APP_UID)))
        body = r.json() if r.status_code == 200 else {}
        code = body.get("confirmation_code", "")
        check("F1 200 com url e confirmation_code", r.status_code == 200 and set(body) == {"url", "confirmation_code"}, r.text)
        check("F2 codigo alfanumerico (16, A-Z0-9)", re.fullmatch(r"[A-Z0-9]{16}", code) is not None, code)
        check("F3 url aponta para a pagina publica de status com o codigo",
              body.get("url") == f"https://api.test/omni/data-deletion-status?code={code}", body.get("url"))
        check("F4 conversas, mensagens e comentarios do canal apagados", tenant_counts(demo, ep1) == (0, 0, 0), tenant_counts(demo, ep1))
        check("F5 dado de OUTRO tenant intacto", tenant_counts(mdp, str(ep_outro)) == (1, 1, 0), tenant_counts(mdp, str(ep_outro)))
        c = conexao()
        check("F6 canal inativo e anonimizado (sem @usuario, ID, nome real)",
              c["ativo"] is False and c["ig"] is None and c["usr"] is None and c["nome"] == "Removed channel", dict(c))
        check("F7 metadados da conexao limpos", c["metadados"] == {}, c["metadados"])
        pe = pedidos("EXCLUSAO")
        check("F8 pedido EXCLUSAO CONCLUIDO com 1 canal", len(pe) == 1 and pe[0]["status"] == "CONCLUIDO" and pe[0]["canais_afetados"] == 1, [dict(x) for x in pe])
        r = post_form("/api/meta/data-deletion", signed_request(payload_for(APP_UID)))
        check("F9 repetir: 200, novo codigo, SEM_CORRESPONDENCIA (nada mais a apagar)",
              r.status_code == 200 and r.json()["confirmation_code"] != code
              and [x for x in pedidos("EXCLUSAO") if x["codigo"] == r.json()["confirmation_code"]][0]["status"] == "SEM_CORRESPONDENCIA")

        # ------------------------------------------------------------------ G. casamento pelo ID que roteia o webhook
        print("\n[G] Casamento pelo ID da conta (ig_id)")
        ep2 = connect_demo()
        check("G1 reconexao cria canal novo (o anterior foi anonimizado)", ep2 != ep1)
        db.execute(text("update canal_conexoes set metadados = '{}'::jsonb where endpoint_id = :e"), {"e": ep2}); db.commit()  # como o @mdpdemo de hoje: sem app_user_id
        seed_data(ep2)
        r = post_form("/api/meta/data-deletion", signed_request(payload_for(IG_ID)))
        check("G2 pedido com o ig_id (sem app_user_id gravado) tambem apaga", r.status_code == 200 and tenant_counts(demo, ep2) == (0, 0, 0), tenant_counts(demo, ep2))
        r = post_form("/api/meta/data-deletion", signed_request(payload_for(UNKNOWN_UID)))
        cu = r.json().get("confirmation_code", "")
        pu = [x for x in pedidos("EXCLUSAO") if x["codigo"] == cu]
        check("G3 usuario desconhecido: 200 + codigo + SEM_CORRESPONDENCIA", r.status_code == 200 and len(pu) == 1 and pu[0]["status"] == "SEM_CORRESPONDENCIA")

        # ------------------------------------------------------------------ H. falha do banco do tenant e nova tentativa
        print("\n[H] Falha do banco do tenant")
        ep3 = connect_demo()
        seed_data(ep3)
        db.execute(text("update tenant_databases set ativo = FALSE where tenant_id = :t"), {"t": str(demo)}); db.commit()
        r = post_form("/api/meta/data-deletion", signed_request(payload_for(APP_UID)))
        check("H1 tenant indisponivel -> 500 (a Meta pode tentar de novo)", r.status_code == 500, r.status_code)
        pend = [x for x in pedidos("EXCLUSAO") if x["status"] == "RECEBIDO"]
        check("H2 o pedido fica RECEBIDO (nao finge conclusao)", len(pend) == 1, [dict(x) for x in pedidos("EXCLUSAO")])
        db.execute(text("update tenant_databases set ativo = TRUE where tenant_id = :t"), {"t": str(demo)}); db.commit()
        r = post_form("/api/meta/data-deletion", signed_request(payload_for(APP_UID)))
        check("H3 nova tentativa conclui e apaga", r.status_code == 200 and tenant_counts(demo, ep3) == (0, 0, 0), r.status_code)

        # ------------------------------------------------------------------ I. pagina publica de status
        print("\n[I] Pagina publica de status")
        code_ok = r.json()["confirmation_code"]
        pg = client.get("/omni/data-deletion-status", params={"code": code_ok})
        check("I1 pedido concluido: 200 HTML com codigo, 'Completed', ingles e portugues",
              pg.status_code == 200 and "text/html" in pg.headers["content-type"] and code_ok in pg.text and "Completed" in pg.text
              and "was deleted on" in pg.text and "foram excluídos" in pg.text, pg.status_code)
        check("I2 sem cache e sem indexacao", pg.headers.get("cache-control") == "no-store" and "noindex" in pg.text)
        check("I3 codigo desconhecido -> 404", client.get("/omni/data-deletion-status", params={"code": "ABCDEF0123456789"}).status_code == 404)
        inj = client.get("/omni/data-deletion-status", params={"code": "<script>alert(1)</script>"})
        check("I4 codigo malicioso -> 404 e sem eco do HTML cru", inj.status_code == 404 and "<script>alert(1)</script>" not in inj.text)
        check("I5 sem codigo -> 404", client.get("/omni/data-deletion-status").status_code == 404)
        cod_deauth = pedidos("DESAUTORIZACAO")[0]["codigo"]
        check("I6 codigo de desautorizacao nao aparece na pagina de exclusao", client.get("/omni/data-deletion-status", params={"code": cod_deauth}).status_code == 404)
        sem = [x for x in pedidos("EXCLUSAO") if x["status"] == "SEM_CORRESPONDENCIA"][0]["codigo"]
        ps = client.get("/omni/data-deletion-status", params={"code": sem})
        check("I7 SEM_CORRESPONDENCIA mostra 'Nothing to delete'", ps.status_code == 200 and "Nothing to delete" in ps.text)

        # ------------------------------------------------------------------ J. higiene de log
        print("\n[J] Higiene de log")
        blob = "\n".join(logcap.lines)
        check("J1 nenhum token nem segredo nos logs", all(s not in blob for s in ("SHORTTOKEN", "LONGTOKEN", SECRET_IG, SECRET_MAIN)))
        check("J2 nenhum conteudo de mensagem nos logs", all(s not in blob for s in ("private message", "private comment", "open on Sunday")))
        check("J3 ha log dos pedidos (so IDs e contagens)", "meta_exclusao meta_user_id=" in blob and "meta_deauth meta_user_id=" in blob)
    finally:
        db.rollback()
        logging.getLogger().removeHandler(logcap)
        for k, v in saved.items():
            setattr(settings, k, v)
        # limpeza (so dados de teste)
        try:
            db.execute(text("update tenant_databases set ativo = TRUE where tenant_id = any(:t)"), {"t": [str(demo), str(mdp)]})
            for ep in endpoints:
                for tid in (demo, mdp):
                    try:
                        with tenant_session(db, tid) as t:
                            omni_store.delete_endpoint_data(t, ep)
                    except Exception:  # noqa: BLE001
                        pass
            db.execute(text("delete from tenant_endpoints where codigo like 'INSTAGRAM_PRIVACY_TEST%'"))
            db.execute(text("delete from meta_pedidos_privacidade where meta_user_id = any(:ids)"), {"ids": list(ids_testados)})
            db.execute(text("delete from usuarios where email = :e"), {"e": EMAIL})
            db.commit()
        finally:
            db.close()

    ok, total = sum(resultados), len(resultados)
    print(f"\n{ok}/{total} verificacoes OK")
    sys.exit(0 if ok == total else 1)


if __name__ == "__main__":
    main()
