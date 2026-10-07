"""
Provisiona o tenant "MDP Demo" (banco proprio) e o usuario de revisao da Meta.

SEGURANCA / COMO USAR
  * Por padrao NAO altera nada (dry-run): so mostra o plano e valida pre-requisitos.
  * Para executar:  --executar   (e, em producao, tambem --ambiente prod --confirmo-prod)
  * Idempotente: pode ser repetido; cada passo verifica se ja existe.
  * Credenciais: DATABASE_URL vem do ambiente/.env (nunca e impressa). A senha do usuario
    de revisao vem de REVIEW_USER_PASSWORD; se ausente, e gerada e mostrada UMA vez.
  * Ordem: banco do tenant primeiro, registro na plataforma por ULTIMO (uma execucao
    interrompida nunca deixa a plataforma apontando para um banco quebrado).

PRE-REQUISITOS
  * Migration platform 010 aplicada em mdp_platform.
  * O usuario do PostgreSQL da aplicacao (mdp) precisa de permissao CREATEDB
    (ou crie o banco vazio antes: o script detecta e segue).
  * Rodar na raiz do projeto mdp-api (usa app.security.password para o hash da senha).

EXEMPLOS
  python scripts/provisionar_tenant_demo.py --review-email revisao.meta@mdpconsultoria.com.br --superadmin-email <seu-email>
  python scripts/provisionar_tenant_demo.py ... --executar
  python scripts/provisionar_tenant_demo.py --encerrar-revisao --review-email <email> --executar
"""
from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

try:  # .env opcional (o projeto ja usa python-dotenv)
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    pass

PROTEGIDOS = {"mdp", "tenant_mdp", "mdp_platform", "postgres", "template0", "template1"}
FUNCIONALIDADE_OMNI = "CRM_OMNI"


# ----------------------------------------------------------------------------- utilidades
def hash_password(pwd: str) -> str:
    try:
        from app.security.password import hash_password as hp
        return hp(pwd)
    except Exception:
        from pwdlib import PasswordHash
        return PasswordHash.recommended().hash(pwd)


def base_dsn() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL nao definida (ambiente ou .env).")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def conectar(dbname: str, autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(make_conninfo(base_dsn(), dbname=dbname), autocommit=autocommit, connect_timeout=8)


def alvo_publico() -> dict:
    d = conninfo_to_dict(base_dsn())
    return {"host": d.get("host", "?"), "port": d.get("port", "5432"), "user": d.get("user", "?")}


def ler_sql(path: Path) -> str:
    texto = path.read_text(encoding="utf-8")
    linhas = [l for l in texto.replace("\r\n", "\n").split("\n")
              if not re.match(r"^\\(un)?restrict|^SET transaction_timeout", l)]
    return "\n".join(linhas)


def existe_banco(nome: str) -> bool:
    with conectar("postgres", autocommit=True) as c:
        return c.execute("SELECT 1 FROM pg_database WHERE datname=%s", (nome,)).fetchone() is not None


def existe_tabela(conn, tabela: str) -> bool:
    return conn.execute("SELECT to_regclass(%s)", (f"public.{tabela}",)).fetchone()[0] is not None


def existe_coluna(conn, tabela: str, coluna: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=%s AND column_name=%s",
        (tabela, coluna)).fetchone() is not None


def passo(msg: str) -> None:
    print(f"  - {msg}")


def verificar_prerequisitos(a) -> None:
    """Falha ANTES de criar qualquer coisa se a migration 010 da plataforma nao foi aplicada."""
    with conectar(a.platform_db) as p:
        for tabela, coluna in (("usuarios", "mfa_dispensado"), ("usuarios", "acesso_expira_em"), ("canal_conexoes", "id")):
            if not existe_coluna(p, tabela, coluna):
                sys.exit("Migration 010 da plataforma NAO aplicada (faltam colunas/tabelas). Aplique-a antes.")
        if a.superadmin_email and not p.execute(
                "SELECT 1 FROM usuarios WHERE lower(email)=lower(%s) AND is_superadmin AND ativo",
                (a.superadmin_email,)).fetchone():
            sys.exit("SUPERADMIN ativo nao encontrado para o e-mail informado.")


# ----------------------------------------------------------------------------- tenant (banco proprio)
def provisionar_banco_tenant(a, executar: bool) -> None:
    print(f"\n[1/3] Banco do tenant '{a.database}'")
    if not existe_banco(a.database):
        passo(f"CRIAR banco {a.database}")
        if executar:
            with conectar("postgres", autocommit=True) as c:
                c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(a.database)))
    else:
        passo("banco ja existe (ok)")
    if not executar and not existe_banco(a.database):
        passo("(dry-run) baseline, migration 006 e seed de catalogos seriam aplicados")
        return

    baseline = a.baseline
    mig006 = PROJECT_ROOT / "database/tenant/migrations/006_omni_mensagens_comentarios.sql"
    seed = PROJECT_ROOT / "database/tenant/seeds/001_catalogos.sql"
    for f in (baseline, mig006, seed):
        if not f.exists():
            sys.exit(f"Arquivo nao encontrado: {f}")

    with conectar(a.database) as c:
        tem_base = existe_tabela(c, "empresas")
    passo("baseline de esquema: " + ("ja aplicado (ok)" if tem_base else f"APLICAR {baseline.name}"))
    if not tem_base and executar:
        with conectar(a.database) as c:      # conexao propria: o dump zera o search_path
            c.execute(ler_sql(baseline))
    for arq in (mig006, seed):
        passo(f"aplicar {arq.name} (idempotente)")
        if executar:
            with conectar(a.database) as c:
                c.execute(ler_sql(arq))


def provisionar_dados_tenant(a, usuarios: list[dict], executar: bool) -> dict:
    """usuarios: [{'platform_id': uuid, 'perfil': 'ADMIN'|'OMNI_OPERADOR'}]"""
    print("\n[3/3] Dados operacionais do tenant (empresa, perfis, usuarios locais)")
    passo(f"empresa '{a.nome}' (slug '{a.empresa_slug}')")
    for u in usuarios:
        passo(f"usuario {u['platform_id']} -> perfil {u['perfil']}")
    if not executar:
        return {}
    with conectar(a.database) as c:
        c.execute("""INSERT INTO perfis (codigo,nome,descricao,ativo,acesso_total)
                     VALUES ('ADMIN','Administrador','Acesso total as funcionalidades habilitadas para o Tenant',TRUE,TRUE)
                     ON CONFLICT (codigo) DO NOTHING""")
        emp = c.execute("""INSERT INTO empresas (nome,slug,ativo,status,organizacao_principal)
                           VALUES (%s,%s,TRUE,'CLIENTE',TRUE)
                           ON CONFLICT (slug) DO UPDATE SET nome=EXCLUDED.nome
                           RETURNING id""", (a.nome, a.empresa_slug)).fetchone()[0]
        for u in usuarios:
            ut = c.execute("""INSERT INTO usuarios_tenant (platform_usuario_id,ativo) VALUES (%s,TRUE)
                              ON CONFLICT (platform_usuario_id) DO UPDATE SET ativo=TRUE RETURNING id""",
                           (u["platform_id"],)).fetchone()[0]
            perfil = c.execute("SELECT id FROM perfis WHERE codigo=%s", (u["perfil"],)).fetchone()
            if not perfil:
                raise RuntimeError(f"Perfil {u['perfil']} nao existe no tenant (migration 006 aplicada?)")
            c.execute("""INSERT INTO usuarios_empresas
                           (usuario_id,empresa_id,perfil_id,ativo,acesso_todas_unidades,acesso_todas_areas)
                         VALUES (%s,%s,%s,TRUE,TRUE,TRUE)
                         ON CONFLICT (usuario_id,empresa_id) DO UPDATE SET perfil_id=EXCLUDED.perfil_id, ativo=TRUE""",
                      (ut, emp, perfil[0]))
    return {"empresa_id": emp}


# ----------------------------------------------------------------------------- plataforma
def provisionar_plataforma(a, executar: bool) -> list[dict]:
    print("\n[2/3] Plataforma (mdp_platform): tenant, banco, funcionalidade, usuarios")
    d = conninfo_to_dict(base_dsn())
    with conectar(a.platform_db) as p:
        for tabela, coluna in (("usuarios", "mfa_dispensado"), ("usuarios", "acesso_expira_em"), ("canal_conexoes", "id")):
            if not existe_coluna(p, tabela, coluna):
                sys.exit("Migration 010 da plataforma NAO aplicada (faltam colunas/tabelas). Aplique-a antes.")
        sa = None
        if a.superadmin_email:
            sa = p.execute("SELECT id FROM usuarios WHERE lower(email)=lower(%s) AND is_superadmin AND ativo",
                           (a.superadmin_email,)).fetchone()
            if not sa:
                sys.exit(f"SUPERADMIN ativo nao encontrado para o e-mail informado.")

    passo(f"tenant {a.codigo} / slug {a.slug} / banco {a.database} (MDP_SHARED)")
    passo(f"funcionalidade {FUNCIONALIDADE_OMNI} habilitada")
    passo(f"usuario de revisao {a.review_email} (MFA dispensado, validade {a.review_dias} dias, perfil OMNI_OPERADOR)")
    if a.superadmin_email:
        passo("SUPERADMIN vinculado ao tenant (perfil ADMIN) para depuracao")
    if not executar:
        return []

    senha = os.environ.get("REVIEW_USER_PASSWORD")
    gerada = False
    if not senha:
        senha, gerada = secrets.token_urlsafe(18), True
    if len(senha) < 12:
        sys.exit("REVIEW_USER_PASSWORD precisa ter ao menos 12 caracteres.")
    expira = datetime.now(timezone.utc) + timedelta(days=a.review_dias)

    with conectar(a.platform_db) as p:
        tid = p.execute("""INSERT INTO tenants (codigo,nome,slug,ativo,tenant_sistema) VALUES (%s,%s,%s,TRUE,FALSE)
                           ON CONFLICT (codigo) DO UPDATE SET nome=EXCLUDED.nome RETURNING id""",
                        (a.codigo, a.nome, a.slug)).fetchone()[0]
        p.execute("""INSERT INTO tenant_databases (tenant_id,tipo_infra,host,porta,database_name,username,versao_schema,ativo)
                     VALUES (%s,'MDP_SHARED',%s,%s,%s,%s,'omni-006',TRUE)
                     ON CONFLICT (tenant_id) DO UPDATE SET database_name=EXCLUDED.database_name, ativo=TRUE""",
                  (tid, d.get("host", "localhost"), int(d.get("port", 5432)), a.database, d.get("user", "mdp")))
        p.execute("""INSERT INTO tenant_branding (tenant_id,nome_exibicao,ativo) VALUES (%s,%s,TRUE)
                     ON CONFLICT (tenant_id) DO NOTHING""", (tid, a.nome))
        fun = p.execute("SELECT id FROM funcionalidades WHERE codigo=%s", (FUNCIONALIDADE_OMNI,)).fetchone()
        if fun:
            p.execute("""INSERT INTO tenants_funcionalidades (tenant_id,funcionalidade_id,ativo) VALUES (%s,%s,TRUE)
                         ON CONFLICT (tenant_id,funcionalidade_id) DO UPDATE SET ativo=TRUE, desabilitado_em=NULL""",
                      (tid, fun[0]))
        else:
            print(f"  ! funcionalidade {FUNCIONALIDADE_OMNI} nao cadastrada: habilite manualmente depois.")

        rev = p.execute("SELECT id FROM usuarios WHERE lower(email)=lower(%s)", (a.review_email,)).fetchone()
        if rev:
            rev_id = rev[0]
            p.execute("""UPDATE usuarios SET ativo=TRUE, mfa_dispensado=TRUE, acesso_expira_em=%s, updated_at=now()
                         WHERE id=%s AND NOT is_superadmin""", (expira, rev_id))
            gerada = False
            senha = None   # usuario ja existia: a senha NAO e alterada
        else:
            rev_id = p.execute("""INSERT INTO usuarios (nome,email,password_hash,is_superadmin,ativo,mfa_dispensado,acesso_expira_em)
                                  VALUES ('Meta App Review',%s,%s,FALSE,TRUE,TRUE,%s) RETURNING id""",
                               (a.review_email.lower().strip(), hash_password(senha), expira)).fetchone()[0]
        usuarios = [{"user_id": rev_id, "perfil": "OMNI_OPERADOR"}]
        if sa:
            usuarios.append({"user_id": sa[0], "perfil": "ADMIN"})
        for u in usuarios:
            p.execute("""INSERT INTO usuarios_tenants (usuario_id,tenant_id,ativo) VALUES (%s,%s,TRUE)
                         ON CONFLICT (usuario_id,tenant_id) DO UPDATE SET ativo=TRUE""", (u["user_id"], tid))
    if gerada:
        print(f"\n  >>> SENHA GERADA para {a.review_email} (mostrada uma unica vez): {senha}")
    return [{"platform_id": u["user_id"], "perfil": u["perfil"]} for u in usuarios]


def encerrar_revisao(a, executar: bool) -> None:
    print("\nEncerrar acesso de revisao")
    passo(f"desativar {a.review_email}, revogar sessoes e desativar vinculos de tenant")
    if not executar:
        return
    with conectar(a.platform_db) as p:
        r = p.execute("""UPDATE usuarios SET ativo=FALSE, updated_at=now()
                         WHERE lower(email)=lower(%s) AND NOT is_superadmin RETURNING id""", (a.review_email,)).fetchone()
        if not r:
            sys.exit("Usuario nao encontrado (ou e SUPERADMIN: nunca desativado por este script).")
        p.execute("UPDATE sessoes_usuario SET revogada_em=now(), motivo_revogacao='REVISAO_ENCERRADA' "
                  "WHERE usuario_id=%s AND revogada_em IS NULL", (r[0],))
        p.execute("UPDATE usuarios_tenants SET ativo=FALSE WHERE usuario_id=%s", (r[0],))
    print("  ok.")


# ----------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--executar", action="store_true", help="aplica de verdade (padrao: dry-run)")
    ap.add_argument("--ambiente", choices=["local", "prod"], default="local")
    ap.add_argument("--confirmo-prod", action="store_true")
    ap.add_argument("--platform-db", default=os.environ.get("PLATFORM_DATABASE_NAME", "mdp_platform"))
    ap.add_argument("--codigo", default="MDP_DEMO")
    ap.add_argument("--slug", default="mdp-demo")
    ap.add_argument("--nome", default="MDP Demo")
    ap.add_argument("--database", default="tenant_mdp_demo")
    ap.add_argument("--empresa-slug", default="demo")
    ap.add_argument("--baseline", type=Path,
                    default=PROJECT_ROOT / "database/tenant/baseline/tenant_baseline_20261002.sql")
    ap.add_argument("--review-email")
    ap.add_argument("--review-dias", type=int, default=30)
    ap.add_argument("--superadmin-email",
                    help="OPCIONAL e arriscado: vincula o SUPERADMIN ao Demo. Com 2 tenants, o login atual "
                         "(sem seletor de tenant) devolve 409 e o SUPERADMIN deixa de entrar no tenant MDP. "
                         "Exige --confirmo-superadmin-multitenant.")
    ap.add_argument("--confirmo-superadmin-multitenant", action="store_true")
    ap.add_argument("--encerrar-revisao", action="store_true")
    ap.add_argument("--desvincular-superadmin", metavar="EMAIL",
                    help="remove o vinculo do SUPERADMIN com o tenant informado em --codigo (reversao)")
    a = ap.parse_args()

    if not a.desvincular_superadmin and not a.review_email:
        sys.exit("--review-email e obrigatorio.")
    if a.database in PROTEGIDOS:
        sys.exit(f"Recusado: '{a.database}' e um banco protegido.")
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,62}", a.database):
        sys.exit("Nome de banco invalido (use minusculas, numeros e _).")
    if a.executar and a.ambiente == "prod" and not a.confirmo_prod:
        sys.exit("Em prod e obrigatorio --confirmo-prod (valide antes em DEV).")
    if a.superadmin_email and not a.confirmo_superadmin_multitenant:
        sys.exit("Recusado: vincular o SUPERADMIN a um segundo tenant quebra o login dele no tenant MDP enquanto o front "
                 "nao enviar tenant_id / nao tiver seletor de contexto. Omita --superadmin-email ou confirme com "
                 "--confirmo-superadmin-multitenant (e saiba reverter: --desvincular-superadmin).")
    if not 1 <= a.review_dias <= 90:
        sys.exit("--review-dias deve estar entre 1 e 90.")

    t = alvo_publico()
    print(f"Ambiente: {a.ambiente} | servidor {t['host']}:{t['port']} (usuario {t['user']}) | "
          f"plataforma={a.platform_db} tenant={a.database}")
    print("MODO: " + ("EXECUCAO" if a.executar else "DRY-RUN (nada sera alterado)"))

    if a.desvincular_superadmin:
        print(f"\nDesvincular SUPERADMIN do tenant {a.codigo}")
        if a.executar:
            with conectar(a.platform_db) as p:
                n = p.execute("""UPDATE usuarios_tenants SET ativo=FALSE
                                 WHERE usuario_id=(SELECT id FROM usuarios WHERE lower(email)=lower(%s) AND is_superadmin)
                                   AND tenant_id=(SELECT id FROM tenants WHERE codigo=%s)""",
                              (a.desvincular_superadmin, a.codigo)).rowcount
            print(f"  vinculos desativados: {n}")
        return

    if a.encerrar_revisao:
        encerrar_revisao(a, a.executar)
        return

    verificar_prerequisitos(a)
    provisionar_banco_tenant(a, a.executar)
    usuarios = provisionar_plataforma(a, a.executar)
    # o vinculo local no tenant depende dos IDs centrais criados acima
    if a.executar:
        provisionar_dados_tenant(a, usuarios, True)
    else:
        provisionar_dados_tenant(a, [], False)
    print("\nConcluido." if a.executar else "\nDry-run concluido. Reexecute com --executar para aplicar.")


if __name__ == "__main__":
    main()
