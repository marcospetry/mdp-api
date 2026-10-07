"""
Teste automatico do login do revisor da Meta (mfa_dispensado) + regressao do login atual.

ONDE RODAR: SOMENTE em banco de TESTE/DEV descartavel. Cria e remove usuarios com e-mails
@exemplo-teste.com.br. Nao toca em usuarios reais. Nao imprime tokens nem senhas.

Pre-requisitos (todos ja existem apos aplicar as migrations 010/006 e o script do Demo):
  * mdp_platform com a migration 010; tenants MDP e MDP_DEMO provisionados.
  * Variaveis de ambiente: DATABASE_URL (base do servidor), PLATFORM_DATABASE_NAME,
    SECRET_KEY, MFA_ENCRYPTION_KEY.
  * Um SUPERADMIN de teste e um usuario comum de teste ja criados e vinculados ao tenant MDP
    (o proprio script os cria se estiver usando --criar-fixtures).

Uso:
    python scripts/test_login_revisor.py --criar-fixtures
"""
from __future__ import annotations

import argparse
import sys
from uuid import uuid4
from datetime import timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.database import PlatformSessionLocal
from app.main import app
from app.models.platform_auth import PlatformTenant, PlatformUsuario, PlatformUsuarioTenant
from app.security.password import hash_password
from app.services.auth_service import utcnow

SENHA = "SenhaTeste#12345"
EMAILS = {
    "super": "t.super@exemplo-teste.com.br",
    "comum": "t.comum@exemplo-teste.com.br",
    "revisor": "t.revisor@exemplo-teste.com.br",
    "revisor_sem_tenant": "t.revisor.semtenant@exemplo-teste.com.br",
}
client = TestClient(app)
resultados: list[tuple[str, bool, str]] = []


def check(nome: str, cond: bool, detalhe: str = "") -> None:
    resultados.append((nome, bool(cond), detalhe))
    print(("  OK   " if cond else "  FALHA") + f"  {nome}" + (f"  [{detalhe}]" if detalhe and not cond else ""))


def login(email, senha=SENHA, plataforma=False, tenant_id=None):
    body = {"email": email, "senha": senha, "contexto_plataforma": plataforma}
    if tenant_id:
        body["tenant_id"] = str(tenant_id)
    return client.post("/api/auth/login", json=body)


def auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def mfa_completo(email, plataforma):
    """Login de usuario com MFA (setup na 1a vez, verify depois). Devolve (access, refresh, secret|None)."""
    r = login(email, plataforma=plataforma)
    st, pre = r.json().get("status"), r.json().get("preauth_token")
    secret = None
    if st == "MFA_SETUP":
        secret = client.post(f"/api/auth/mfa/setup?preauth_token={pre}").json()["secret"]
    elif st != "MFA_VERIFY":
        return None, None, r
    if secret is None:
        return None, None, r
    v = client.post("/api/auth/mfa/verify", json={"preauth_token": pre, "codigo": pyotp.TOTP(secret).now()})
    return v.json().get("access_token"), v.json().get("refresh_token"), v


def mfa_verify(email, secret, plataforma):
    r = login(email, plataforma=plataforma)
    pre = r.json().get("preauth_token")
    v = client.post("/api/auth/mfa/verify", json={"preauth_token": pre, "codigo": pyotp.TOTP(secret).now()})
    return r, v


def fixtures(db):
    tenants = {t.codigo: t for t in db.query(PlatformTenant).all()}
    mdp, demo = tenants["MDP"], tenants["MDP_DEMO"]
    return mdp, demo


def exigir_ambiente_de_teste():
    """Trava de seguranca: estes scripts criam usuarios com senha conhecida. So rodam com APP_ENV de desenvolvimento/teste."""
    from app.config import settings
    if settings.app_env.strip().lower() not in ("development", "dev", "test", "local"):
        sys.exit("Recusado: APP_ENV='%s'. Este script cria usuarios de teste e so pode rodar em DEV/teste (APP_ENV=development)." % settings.app_env)


def main():
    exigir_ambiente_de_teste()
    ap = argparse.ArgumentParser()
    ap.add_argument("--criar-fixtures", action="store_true")
    a = ap.parse_args()

    db = PlatformSessionLocal()
    mdp, demo = fixtures(db)
    ids = {}

    try:
        print("\n[0] Fixtures")
        if a.criar_fixtures:
            from app.database import tenant_session
            from app.models.auth import UsuarioEmpresa, UsuarioTenantLocal
            from app.models.empresa import Empresa
            from sqlalchemy import text

            def novo(email, nome, superadmin=False, dispensado=False):
                u = PlatformUsuario(nome=nome, email=email, password_hash=hash_password(SENHA),
                                    is_superadmin=superadmin, mfa_dispensado=dispensado,
                                    acesso_expira_em=(utcnow() + timedelta(days=30)) if dispensado else None)
                db.add(u); db.flush(); ids[email] = u.id
                return u
            su = novo(EMAILS["super"], "Super Teste", superadmin=True)
            co = novo(EMAILS["comum"], "Comum Teste")
            rv = novo(EMAILS["revisor"], "Revisor Teste", dispensado=True)
            rs = novo(EMAILS["revisor_sem_tenant"], "Revisor sem tenant", dispensado=True)
            for u in (su, co):
                db.add(PlatformUsuarioTenant(id=uuid4(), usuario_id=u.id, tenant_id=mdp.id, ativo=True))
            db.add(PlatformUsuarioTenant(id=uuid4(), usuario_id=rv.id, tenant_id=demo.id, ativo=True))
            db.commit()
            # usuarios locais nos tenants (empresa + perfil)
            with tenant_session(db, mdp.id) as t:
                emp = t.query(Empresa).first()
                perfil_admin = t.execute(text("select id from perfis where codigo='ADMIN'")).scalar()
                for u in (su, co):
                    loc = UsuarioTenantLocal(platform_usuario_id=u.id, ativo=True); t.add(loc); t.flush()
                    t.add(UsuarioEmpresa(usuario_id=loc.id, empresa_id=emp.id, perfil_id=perfil_admin,
                                         ativo=True, acesso_todas_unidades=True, acesso_todas_areas=True))
                t.commit()
            with tenant_session(db, demo.id) as t:
                emp = t.query(Empresa).first()
                perfil_op = t.execute(text("select id from perfis where codigo='OMNI_OPERADOR'")).scalar()
                loc = UsuarioTenantLocal(platform_usuario_id=rv.id, ativo=True); t.add(loc); t.flush()
                t.add(UsuarioEmpresa(usuario_id=loc.id, empresa_id=emp.id, perfil_id=perfil_op,
                                     ativo=True, acesso_todas_unidades=True, acesso_todas_areas=True))
                t.commit()
            print("  fixtures criadas")

        # ---------------------------------------------------------------- A. regressao SUPERADMIN
        print("\n[A] Regressao: login do SUPERADMIN (Plataforma e tenant MDP), com 2 tenants na plataforma")
        r = login(EMAILS["super"], plataforma=True)
        check("A1 SUPERADMIN + checkbox Plataforma pede MFA (MFA_SETUP no 1o acesso)", r.status_code == 200 and r.json()["status"] == "MFA_SETUP", r.text[:120])
        acc, ref, v = mfa_completo(EMAILS["super"], plataforma=True)
        check("A2 MFA conclui e autentica na Plataforma", acc is not None, getattr(v, "text", "")[:120])
        me = client.get("/api/auth/me", headers=auth(acc)).json() if acc else {}
        check("A3 /me: contexto PLATAFORMA e permissao PLATAFORMA_ADMIN", me.get("contexto_tipo") == "PLATAFORMA" and me.get("permissoes") == ["PLATAFORMA_ADMIN"], str(me)[:150])
        lst = client.get("/api/platform/tenants/", headers=auth(acc)) if acc else None
        codigos = sorted(t["codigo"] for t in lst.json()) if lst is not None and lst.status_code == 200 else []
        check("A4 Plataforma lista os 2 tenants (MDP e MDP_DEMO)", codigos == ["MDP", "MDP_DEMO"], str(codigos))
        secret = None
        # recupera o segredo gravado para repetir o login como o usuario real faria
        from app.security.mfa import decrypt_secret
        db.expire_all()
        su = db.query(PlatformUsuario).filter(PlatformUsuario.email == EMAILS["super"]).first()
        secret = decrypt_secret(su.mfa_secret_enc)
        r, v = mfa_verify(EMAILS["super"], secret, plataforma=False)
        check("A5 SUPERADMIN SEM checkbox pede MFA (MFA_VERIFY) e NAO recebe 409 de multiplos tenants", r.status_code == 200 and r.json()["status"] == "MFA_VERIFY", r.text[:120])
        acc_t = v.json().get("access_token")
        check("A6 MFA conclui e autentica no tenant MDP", acc_t is not None, v.text[:120])
        me = client.get("/api/auth/me", headers=auth(acc_t)).json() if acc_t else {}
        check("A7 /me: contexto TENANT, tenant 'MDP Consultoria', perfil ADMIN", me.get("contexto_tipo") == "TENANT" and me.get("tenant_nome") == "MDP Consultoria" and me.get("perfil") == "ADMIN", str(me)[:150])
        emp = client.get("/api/admin/empresas", headers=auth(acc_t)) if acc_t else None
        check("A8 SUPERADMIN no tenant MDP lista empresas normalmente", emp is not None and emp.status_code == 200, str(getattr(emp, "status_code", None)))
        rf = client.post("/api/auth/refresh", json={"refresh_token": ref}) if ref else None
        check("A9 refresh do SUPERADMIN continua funcionando", rf is not None and rf.status_code == 200, str(getattr(rf, "status_code", None)))

        # ---------------------------------------------------------------- B. usuario comum sem MFA
        print("\n[B] Regressao: usuario comum sem MFA e sem dispensa continua bloqueado")
        r = login(EMAILS["comum"])
        check("B1 usuario comum sem MFA recebe 409 (comportamento atual preservado)", r.status_code == 409, f"{r.status_code} {r.text[:100]}")
        r = login(EMAILS["comum"], senha="errada")
        check("B2 senha errada = 401", r.status_code == 401, str(r.status_code))

        # ---------------------------------------------------------------- C. revisor
        print("\n[C] Revisor da Meta (mfa_dispensado, tenant Demo)")
        r = login(EMAILS["revisor"], senha="errada")
        check("C1 senha errada = 401", r.status_code == 401)
        r = login(EMAILS["revisor"])
        ok = r.status_code == 200 and r.json().get("status") == "AUTHENTICATED" and r.json().get("access_token")
        check("C2 login do revisor autentica DIRETO (sem MFA)", ok, f"{r.status_code} {r.text[:120]}")
        acc_r, ref_r = r.json().get("access_token"), r.json().get("refresh_token")
        me = client.get("/api/auth/me", headers=auth(acc_r)).json() if acc_r else {}
        check("C3 /me: tenant 'MDP Demo', perfil OMNI_OPERADOR, nao-SUPERADMIN, contexto TENANT",
              me.get("tenant_nome") == "MDP Demo" and me.get("perfil") == "OMNI_OPERADOR" and me.get("is_superadmin") is False and me.get("contexto_tipo") == "TENANT", str(me)[:200])
        check("C4 permissoes do revisor = apenas as 3 do Omni", me.get("permissoes") == ["OMNI_COMENTARIOS", "OMNI_INBOX", "OMNI_INTEGRACOES"], str(me.get("permissoes")))
        # isolamento
        pl = client.get("/api/platform/tenants/", headers=auth(acc_r))
        check("C5 revisor NAO acessa a administracao da Plataforma (403)", pl.status_code == 403, str(pl.status_code))
        em = client.get("/api/admin/empresas", headers=auth(acc_r))
        check("C6 revisor (perfil so-Omni) NAO acessa o backoffice: /api/admin/empresas = 403",
              em.status_code == 403 and "backoffice" in em.text.lower(), f"{em.status_code} {em.text[:80]}")
        r2 = login(EMAILS["revisor"], plataforma=True)
        acc2 = r2.json().get("access_token")
        pl2 = client.get("/api/platform/tenants/", headers=auth(acc2)) if acc2 else None
        check("C7 checkbox 'Plataforma' marcado NAO da acesso de Plataforma ao revisor", pl2 is not None and pl2.status_code == 403, str(getattr(pl2, "status_code", None)))
        r3 = login(EMAILS["revisor"], tenant_id=mdp.id)
        check("C8 revisor NAO consegue escolher o tenant MDP (403)", r3.status_code == 403, f"{r3.status_code} {r3.text[:80]}")
        r4 = login(EMAILS["revisor_sem_tenant"])
        check("C9 revisor sem vinculo de tenant nao entra (403)", r4.status_code == 403, f"{r4.status_code} {r4.text[:80]}")
        # refresh e logout
        rf = client.post("/api/auth/refresh", json={"refresh_token": ref_r})
        check("C10 refresh do revisor funciona", rf.status_code == 200, str(rf.status_code))
        rf_old = client.post("/api/auth/refresh", json={"refresh_token": ref_r})
        check("C11 refresh antigo nao pode ser reutilizado (rotacao)", rf_old.status_code == 401, str(rf_old.status_code))
        acc_new, ref_new = rf.json().get("access_token"), rf.json().get("refresh_token")
        lo = client.post("/api/auth/logout", json={"refresh_token": ref_new}, headers=auth(acc_new))
        check("C12 logout do revisor", lo.status_code == 200, str(lo.status_code))
        check("C13 token apos logout e recusado (401)", client.get("/api/auth/me", headers=auth(acc_new)).status_code == 401)

        # ---------------------------------------------------------------- D. validade
        print("\n[D] Validade do acesso do revisor")
        r = login(EMAILS["revisor"])
        tok, ref_v = r.json().get("access_token"), r.json().get("refresh_token")
        rev = db.query(PlatformUsuario).filter(PlatformUsuario.email == EMAILS["revisor"]).first()
        rev.acesso_expira_em = utcnow() - timedelta(minutes=1)
        db.commit()
        check("D1 apos vencer: login = 403 'Acesso expirado'", (lambda x: x.status_code == 403 and "expirado" in x.text.lower())(login(EMAILS["revisor"])))
        check("D2 apos vencer: token ja emitido = 401", client.get("/api/auth/me", headers=auth(tok)).status_code == 401)
        check("D3 apos vencer: refresh = 401", client.post("/api/auth/refresh", json={"refresh_token": ref_v}).status_code == 401)
        db.expire_all()
        rev = db.query(PlatformUsuario).filter(PlatformUsuario.email == EMAILS["revisor"]).first()
        rev.acesso_expira_em = utcnow() + timedelta(days=5)
        db.commit()
        check("D4 estendendo a validade, o login volta a funcionar", login(EMAILS["revisor"]).status_code == 200)
        rev.mfa_dispensado = False
        db.commit()
        check("D5 sem a dispensa, o revisor volta a ser bloqueado (409)", login(EMAILS["revisor"]).status_code == 409)
        rev.mfa_dispensado = True
        db.commit()
        # desativado
        rev.ativo = False
        db.commit()
        check("D6 usuario desativado = 401", login(EMAILS["revisor"]).status_code == 401)
        rev.ativo = True
        db.commit()

        # ---------------------------------------------------------------- E. regras do banco
        print("\n[E] Regras do banco")
        try:
            su2 = db.query(PlatformUsuario).filter(PlatformUsuario.email == EMAILS["super"]).first()
            su2.mfa_dispensado = True
            su2.acesso_expira_em = utcnow() + timedelta(days=1)
            db.commit()
            check("E1 banco recusa dispensa de MFA para SUPERADMIN", False, "foi aceito!")
        except IntegrityError:
            db.rollback()
            check("E1 banco recusa dispensa de MFA para SUPERADMIN", True)
        # superadmin nunca usa a dispensa, mesmo que alguem force a flag direto no banco (sem a constraint)
        from app.services.auth_service import mfa_dispensa_valida
        class Falso:  # usuario hipotetico: superadmin com flag
            mfa_dispensado = True; is_superadmin = True; mfa_habilitado = False
            acesso_expira_em = utcnow() + timedelta(days=1)
        check("E2 codigo tambem recusa a dispensa para SUPERADMIN (defesa em profundidade)", mfa_dispensa_valida(Falso()) is False)
    finally:
        # limpeza das fixtures de teste
        db.rollback()
        from sqlalchemy import text
        from app.database import tenant_session
        emails = list(EMAILS.values())
        uids = [row[0] for row in db.execute(text("select id from usuarios where email = any(:e)"), {"e": emails})]
        for tn in (mdp, demo):
            with tenant_session(db, tn.id) as t:
                for uid in uids:
                    t.execute(text("delete from usuarios_empresas where usuario_id in (select id from usuarios_tenant where platform_usuario_id=:u)"), {"u": uid})
                    t.execute(text("delete from usuarios_tenant where platform_usuario_id=:u"), {"u": uid})
                t.commit()
        for uid in uids:
            db.execute(text("delete from sessoes_usuario where usuario_id=:u"), {"u": uid})
            db.execute(text("delete from usuarios_tenants where usuario_id=:u"), {"u": uid})
            db.execute(text("delete from usuarios where id=:u"), {"u": uid})
        db.commit()
        db.close()

    falhas = [r for r in resultados if not r[1]]
    print(f"\nResumo: {len(resultados) - len(falhas)} ok, {len(falhas)} falha(s) de {len(resultados)} verificacoes.")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
