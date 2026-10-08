"""
Teste automatico da area Omni (API) e do bloqueio de backoffice para perfis so-Omni.

ONDE RODAR: SOMENTE em banco de TESTE/DEV descartavel. Cria e REMOVE usuarios @exemplo-teste.com.br,
um perfil de teste e dados de exemplo do Omni no tenant MDP_DEMO. Nao toca em usuarios reais.
Nao imprime tokens nem senhas.

Uso:  python scripts/test_omni_area.py
Pre-requisitos: migrations 010/006 aplicadas; tenants MDP e MDP_DEMO existentes e provisionados.
"""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import text

import seed_omni_demo
from app.database import PlatformSessionLocal, tenant_session
from app.main import app
from app.models.auth import UsuarioEmpresa, UsuarioTenantLocal
from app.models.empresa import Empresa
from app.models.platform_auth import PlatformTenant, PlatformUsuario, PlatformUsuarioTenant
from app.security.mfa import decrypt_secret
from app.security.password import hash_password
from app.services.auth_service import utcnow
from datetime import timedelta

SENHA = "SenhaTeste#12345"
EMAILS = {"super": "o.super@exemplo-teste.com.br", "rev": "o.revisor@exemplo-teste.com.br", "semomni": "o.semomni@exemplo-teste.com.br"}
client = TestClient(app)
resultados: list[tuple[str, bool]] = []


def check(nome, cond, detalhe=""):
    resultados.append((nome, bool(cond)))
    print(("  OK   " if cond else "  FALHA") + f"  {nome}" + (f"  [{detalhe}]" if detalhe and not cond else ""))


def login(email, plataforma=False):
    return client.post("/api/auth/login", json={"email": email, "senha": SENHA, "contexto_plataforma": plataforma})


def auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def exigir_ambiente_de_teste():
    """Trava de seguranca: estes scripts criam usuarios com senha conhecida. So rodam com APP_ENV de desenvolvimento/teste."""
    from app.config import settings
    if settings.app_env.strip().lower() not in ("development", "dev", "test", "local"):
        sys.exit("Recusado: APP_ENV='%s'. Este script cria usuarios de teste e so pode rodar em DEV/teste (APP_ENV=development)." % settings.app_env)


def main():
    exigir_ambiente_de_teste()
    db = PlatformSessionLocal()
    tenants = {t.codigo: t for t in db.query(PlatformTenant).all()}
    mdp, demo = tenants["MDP"], tenants["MDP_DEMO"]
    perfil_zero = None
    try:
        # ------------------------------------------------------------- fixtures
        print("\n[0] Fixtures e dados de exemplo")
        def novo(email, nome, sup=False, disp=False):
            u = PlatformUsuario(nome=nome, email=email, password_hash=hash_password(SENHA), is_superadmin=sup,
                                mfa_dispensado=disp, acesso_expira_em=(utcnow() + timedelta(days=30)) if disp else None)
            db.add(u); db.flush(); return u
        su, rv, so = novo(EMAILS["super"], "Super", sup=True), novo(EMAILS["rev"], "Revisor", disp=True), novo(EMAILS["semomni"], "Sem Omni", disp=True)
        db.add(PlatformUsuarioTenant(id=uuid4(), usuario_id=su.id, tenant_id=mdp.id, ativo=True))
        for u in (rv, so):
            db.add(PlatformUsuarioTenant(id=uuid4(), usuario_id=u.id, tenant_id=demo.id, ativo=True))
        db.commit()
        with tenant_session(db, mdp.id) as t:
            emp = t.query(Empresa).first()
            admin = t.execute(text("select id from perfis where codigo='ADMIN'")).scalar()
            loc = UsuarioTenantLocal(platform_usuario_id=su.id, ativo=True); t.add(loc); t.flush()
            t.add(UsuarioEmpresa(usuario_id=loc.id, empresa_id=emp.id, perfil_id=admin, ativo=True, acesso_todas_unidades=True, acesso_todas_areas=True))
            t.commit()
        with tenant_session(db, demo.id) as t:
            emp = t.query(Empresa).first()
            op = t.execute(text("select id from perfis where codigo='OMNI_OPERADOR'")).scalar()
            perfil_zero = t.execute(text("insert into perfis(codigo,nome,descricao,ativo,acesso_total) values ('T_SEM_PERMISSAO','Teste sem permissao','x',true,false) returning id")).scalar()
            for u, perfil in ((rv, op), (so, perfil_zero)):
                loc = UsuarioTenantLocal(platform_usuario_id=u.id, ativo=True); t.add(loc); t.flush()
                t.add(UsuarioEmpresa(usuario_id=loc.id, empresa_id=emp.id, perfil_id=perfil, ativo=True, acesso_todas_unidades=True, acesso_todas_areas=True))
            t.commit()
            seed_omni_demo.remove(t)  # parte sempre de um estado conhecido, mesmo com sobras de execucoes anteriores
            print("  dados de exemplo:", seed_omni_demo.seed(t))

        # ------------------------------------------------------------- A. API Omni como revisor
        print("\n[A] API Omni como revisor (perfil OMNI_OPERADOR, tenant Demo)")
        r = login(EMAILS["rev"]); tok = r.json().get("access_token"); H = auth(tok)
        check("A1 revisor entra sem MFA", r.status_code == 200 and tok)
        r = client.get("/api/omni/integrations", headers=H); j = r.json() if r.status_code == 200 else []
        check("A2 integrations: Instagram e Facebook, ambos NOT_CONNECTED", r.status_code == 200 and [(i["provider"], i["status"]) for i in j] == [("INSTAGRAM", "NOT_CONNECTED"), ("FACEBOOK", "NOT_CONNECTED")], r.text[:150])
        check("A3 integrations nao expoe segredos (so campos esperados)", all(set(i) == {"provider", "status", "account_name", "handle", "connected_at", "token_expires_at"} for i in j))
        r = client.get("/api/omni/conversations", headers=H); convs = r.json() if r.status_code == 200 else []
        check("A4 inbox lista 3 conversas, mais recente primeiro", len(convs) == 3 and convs[0]["name"] == "Maria S." and convs[2]["name"] == "Ana C.", r.text[:150])
        check("A5 janela de 24h: aberta p/ Maria e Joao, fechada p/ Ana", [c["reply_window_open"] for c in convs] == [True, True, False])
        check("A6 nao lidas da Maria = 1", convs and convs[0]["unread"] == 1)
        check("A7 filtro por canal (INSTAGRAM=2, FACEBOOK=1)", len(client.get("/api/omni/conversations?channel=INSTAGRAM", headers=H).json()) == 2 and len(client.get("/api/omni/conversations?channel=facebook", headers=H).json()) == 1)
        check("A8 canal desconhecido = 422", client.get("/api/omni/conversations?channel=TIKTOK", headers=H).status_code == 422)
        maria, ana = convs[0]["id"], convs[2]["id"]
        r = client.get(f"/api/omni/conversations/{maria}/messages", headers=H); j = r.json() if r.status_code == 200 else {}
        check("A9 mensagens da conversa em ordem cronologica", r.status_code == 200 and [m["direction"] for m in j.get("messages", [])] == ["ENTRADA", "SAIDA", "ENTRADA"], r.text[:150])
        check("A10 abrir a conversa zera as nao lidas", client.get("/api/omni/conversations", headers=H).json()[0]["unread"] == 0)
        r = client.post(f"/api/omni/conversations/{maria}/reply", json={"text": "  See you Thursday at 10!  "}, headers=H); j = r.json() if r.status_code == 201 else {}
        check("A11 resposta: 201 e NAO marca como enviada (canal nao conectado)", r.status_code == 201 and j.get("status") == "FALHA" and j.get("error") == "channel_not_connected" and j.get("text") == "See you Thursday at 10!", r.text[:150])
        check("A12 a resposta fica registrada na conversa", len(client.get(f"/api/omni/conversations/{maria}/messages", headers=H).json()["messages"]) == 4)
        check("A13 janela fechada = 409", client.post(f"/api/omni/conversations/{ana}/reply", json={"text": "Hi"}, headers=H).status_code == 409)
        check("A14 resposta vazia = 422", client.post(f"/api/omni/conversations/{maria}/reply", json={"text": "   "}, headers=H).status_code == 422)
        check("A15 resposta longa demais = 422", client.post(f"/api/omni/conversations/{maria}/reply", json={"text": "x" * 1001}, headers=H).status_code == 422)
        check("A16 conversa inexistente = 404; id invalido = 422", client.get(f"/api/omni/conversations/{uuid4()}/messages", headers=H).status_code == 404 and client.get("/api/omni/conversations/abc/messages", headers=H).status_code == 422)
        r = client.get("/api/omni/comments", headers=H); cm = r.json() if r.status_code == 200 else []
        check("A17 comments lista 3 itens", r.status_code == 200 and len(cm) == 3, r.text[:120])
        pedro = next((c for c in cm if c["author_name"] == "Pedro L."), {}); carla = next((c for c in cm if c["author_name"] == "Carla M."), {})
        check("A18 comentario ja respondido mostra a resposta", pedro.get("replied") is True and len(pedro.get("replies", [])) == 1)
        r = client.post(f"/api/omni/comments/{carla.get('id')}/reply", json={"text": "Yes, weekends too."}, headers=H); j = r.json() if r.status_code == 201 else {}
        check("A19 resposta a comentario: 201 e FALHA (canal nao conectado)", r.status_code == 201 and j.get("status") == "FALHA" and j.get("error") == "channel_not_connected", r.text[:150])
        carla2 = next(c for c in client.get("/api/omni/comments", headers=H).json() if c["author_name"] == "Carla M.")
        check("A20 resposta aparece sob o comentario e ele NAO vira 'respondido'", len(carla2["replies"]) == 1 and carla2["replied"] is False)
        check("A21 comentario inexistente = 404", client.post(f"/api/omni/comments/{uuid4()}/reply", json={"text": "x"}, headers=H).status_code == 404)
        check("A22 connect = 501 (ainda desligado, Instagram e Facebook); provedor desconhecido = 404",
              client.post("/api/omni/integrations/INSTAGRAM/connect", headers=H).status_code == 501 and client.post("/api/omni/integrations/FACEBOOK/connect", headers=H).status_code == 501 and client.post("/api/omni/integrations/TIKTOK/connect", headers=H).status_code == 404)

        # ------------------------------------------------------------- B. bloqueio do backoffice
        print("\n[B] Revisor NAO acessa o backoffice (cadastros e diagnostico)")
        for rota in ("/api/admin/empresas", "/api/admin/contatos", "/api/diagnostico/categorias", "/api/diagnostico/perguntas"):
            r = client.get(rota, headers=H)
            check(f"B {rota} = 403 'sem acesso ao backoffice'", r.status_code == 403 and "backoffice" in r.text.lower(), f"{r.status_code} {r.text[:80]}")
        check("B Plataforma continua bloqueada (403)", client.get("/api/platform/tenants/", headers=H).status_code == 403)

        # ------------------------------------------------------------- C. perfil sem permissao Omni
        print("\n[C] Perfil sem permissoes nao acessa o Omni")
        r = login(EMAILS["semomni"]); Hs = auth(r.json().get("access_token"))
        for rota in ("/api/omni/integrations", "/api/omni/conversations", "/api/omni/comments"):
            rr = client.get(rota, headers=Hs)
            check(f"C {rota} = 403", rr.status_code == 403 and "Permiss" in rr.text, f"{rr.status_code} {rr.text[:80]}")
        rr = client.get("/api/admin/empresas", headers=Hs)
        print(f"  AVISO  perfil SEM nenhuma permissao ainda acessa /api/admin/empresas (status {rr.status_code}): o bloqueio so cobre perfis exclusivamente OMNI_*. Lacuna pre-existente.")

        # ------------------------------------------------------------- D. sem login
        print("\n[D] Sem autenticacao")
        check("D1 /api/omni/* sem token e recusado", client.get("/api/omni/integrations").status_code in (401, 403))

        # ------------------------------------------------------------- E. regressao SUPERADMIN (ADMIN, acesso_total)
        print("\n[E] Regressao: SUPERADMIN/ADMIN no tenant MDP continua com acesso total")
        r = login(EMAILS["super"]); pre = r.json().get("preauth_token")
        secret = client.post(f"/api/auth/mfa/setup?preauth_token={pre}").json()["secret"]
        v = client.post("/api/auth/mfa/verify", json={"preauth_token": pre, "codigo": pyotp.TOTP(secret).now()})
        He = auth(v.json().get("access_token"))
        check("E1 SUPERADMIN autentica no tenant MDP (MFA)", v.status_code == 200 and He["Authorization"] != "Bearer None")
        for rota in ("/api/admin/empresas", "/api/admin/contatos", "/api/diagnostico/categorias", "/api/diagnostico/perguntas"):
            rr = client.get(rota, headers=He)
            check(f"E {rota} = 200 para ADMIN", rr.status_code == 200, f"{rr.status_code} {rr.text[:80]}")
        for rota in ("/api/omni/integrations", "/api/omni/conversations", "/api/omni/comments"):
            check(f"E {rota} = 200 para ADMIN (acesso_total)", client.get(rota, headers=He).status_code == 200)
    finally:
        db.rollback()
        try:
            with tenant_session(db, demo.id) as t:
                seed_omni_demo.remove(t)
        except Exception:
            pass
        uids = [row[0] for row in db.execute(text("select id from usuarios where email = any(:e)"), {"e": list(EMAILS.values())})]
        for tn in (mdp, demo):
            with tenant_session(db, tn.id) as t:
                for uid in uids:
                    t.execute(text("delete from usuarios_empresas where usuario_id in (select id from usuarios_tenant where platform_usuario_id=:u)"), {"u": uid})
                    t.execute(text("delete from usuarios_tenant where platform_usuario_id=:u"), {"u": uid})
                if tn.id == demo.id:
                    t.execute(text("delete from perfis where codigo='T_SEM_PERMISSAO'"))
                t.commit()
        for uid in uids:
            db.execute(text("delete from sessoes_usuario where usuario_id=:u"), {"u": uid})
            db.execute(text("delete from usuarios_tenants where usuario_id=:u"), {"u": uid})
            db.execute(text("delete from usuarios where id=:u"), {"u": uid})
        db.commit(); db.close()

    falhas = [r for r in resultados if not r[1]]
    print(f"\nResumo: {len(resultados) - len(falhas)} ok, {len(falhas)} falha(s) de {len(resultados)} verificacoes.")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
