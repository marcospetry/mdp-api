"""Conexoes de canais do Omni (plataforma): cadastro do canal + conexao tecnica com token criptografado.

Tudo aqui roda no banco da PLATAFORMA (tenant_endpoints + canal_conexoes). Tokens so existem criptografados.
"""
from __future__ import annotations

import json
import re
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import meta_crypto
from app.services.auth_service import utcnow

ACTIVE = ("CONECTADO", "EXPIRANDO")
_API_STATUS = {"CONECTADO": "CONNECTED", "EXPIRANDO": "EXPIRING", "EXPIRADO": "EXPIRED",
               "REVOGADO": "REVOKED", "ERRO": "ERROR", "PENDENTE": "PENDING"}


class AccountAlreadyConnected(Exception):
    """A conta ja esta conectada a outro tenant."""


class EndpointTypeMissing(Exception):
    """tipos_endpoint nao tem o tipo pedido (INSTAGRAM)."""


def api_status(status: str | None, token_expira_em=None, now=None) -> str:
    """Status do banco (portugues) -> codigo usado pela API e pela tela (ingles)."""
    s = _API_STATUS.get(status or "", "NOT_CONNECTED")
    if s in ("CONNECTED", "EXPIRING") and token_expira_em is not None:
        now = now or utcnow()
        if token_expira_em <= now:
            return "EXPIRED"
        if token_expira_em - now <= timedelta(days=7):
            return "EXPIRING"
    return s


def get_connection(db: Session, tenant_id, provider: str = "INSTAGRAM") -> dict | None:
    row = db.execute(text("""
        SELECT e.id AS endpoint_id, e.nome, e.identificador_externo AS ig_id, e.identificador_publico,
               c.id AS conexao_id, c.status, c.token_expira_em, c.metadados, c.conectado_em, c.webhook_assinado
          FROM tenant_endpoints e
          JOIN tipos_endpoint te ON te.id = e.tipo_endpoint_id
          LEFT JOIN canal_conexoes c ON c.endpoint_id = e.id
         WHERE e.tenant_id = :t AND e.ativo = TRUE AND te.codigo = :p
         ORDER BY (c.status IN ('CONECTADO','EXPIRANDO')) DESC NULLS LAST, e.created_at
         LIMIT 1
    """), {"t": str(tenant_id), "p": provider}).mappings().first()
    return dict(row) if row else None


def upsert_instagram_connection(db: Session, *, tenant_id, user_id, me: dict, long_token: str, expires_in: int,
                                permissions: str, subscribed: bool, webhook_error: str | None = None,
                                app_user_id: str | None = None) -> str:
    """Grava o canal e a conexao do Instagram. Devolve o endpoint_id.

    app_user_id = user_id devolvido na troca do codigo (ID do usuario NO APP). Fica em metadados para os callbacks
    de desautorizacao e de exclusao de dados da Meta acharem o canal.
    """
    username = me.get("username") or ""
    meta = {"name": me.get("name"), "username": username, "account_type": me.get("account_type")}
    return _upsert_channel(
        db, provider="INSTAGRAM", tipo_conexao="INSTAGRAM_LOGIN", token_tipo="IG_LONG_LIVED", tenant_id=tenant_id, user_id=user_id,
        external_id=me["user_id"], handle=username, display_name=me.get("name") or username or f"Instagram {me['user_id']}",
        url=f"https://www.instagram.com/{username}/" if username else None, code_prefix="INSTAGRAM_", token=long_token,
        expires_in=expires_in, permissions=permissions, subscribed=subscribed, webhook_error=webhook_error,
        webhook_fields=["messages", "comments"], meta=meta, app_user_id=app_user_id)


def upsert_facebook_connection(db: Session, *, tenant_id, user_id, page: dict, page_token: str, permissions: str, subscribed: bool,
                               webhook_error: str | None = None, app_user_id: str | None = None) -> str:
    """Grava o canal e a conexao de uma Pagina do Facebook. O token da Pagina nao expira (sem validade nem renovacao).

    app_user_id = ID do usuario NO APP (o 'id' de /me): e o que a Meta manda nos callbacks de desautorizacao e de exclusao.
    O ID da Pagina (identificador_externo) e o que roteia os webhooks (entry.id).
    """
    handle = page.get("username") or ""
    meta = {"name": page.get("name"), "username": handle or None}
    return _upsert_channel(
        db, provider="FACEBOOK", tipo_conexao="FACEBOOK_PAGE", token_tipo="PAGE_TOKEN", tenant_id=tenant_id, user_id=user_id,
        external_id=str(page["id"]), handle=handle, display_name=page.get("name") or f"Facebook {page['id']}",
        url=f"https://www.facebook.com/{handle or page['id']}", code_prefix="FACEBOOK_", token=page_token, expires_in=None,
        permissions=permissions, subscribed=subscribed, webhook_error=webhook_error, webhook_fields=["messages", "feed"],
        meta=meta, app_user_id=app_user_id)


def _upsert_channel(db: Session, *, provider: str, tipo_conexao: str, token_tipo: str, tenant_id, user_id, external_id: str, handle: str,
                    display_name: str, url: str | None, code_prefix: str, token: str, expires_in: int | None, permissions: str,
                    subscribed: bool, webhook_error: str | None, webhook_fields: list[str], meta: dict, app_user_id: str | None) -> str:
    ig_id, username = external_id, handle
    now = utcnow()
    tipo = db.execute(text("SELECT id FROM tipos_endpoint WHERE codigo = :p"), {"p": provider}).scalar()
    if not tipo:
        raise EndpointTypeMissing(provider)

    # 1) a conta ja esta ativa em OUTRO tenant?
    others = db.execute(text("""
        SELECT e.id AS endpoint_id, c.status
          FROM tenant_endpoints e LEFT JOIN canal_conexoes c ON c.endpoint_id = e.id
         WHERE e.tipo_endpoint_id = :tipo AND e.identificador_externo = :ig AND e.ativo = TRUE AND e.tenant_id <> :t
    """), {"tipo": str(tipo), "ig": ig_id, "t": str(tenant_id)}).mappings().all()
    for o in others:
        if o["status"] in ACTIVE:
            raise AccountAlreadyConnected(ig_id)
    for o in others:  # conexao dele ja foi desfeita: libera o identificador para este tenant
        db.execute(text("UPDATE tenant_endpoints SET identificador_externo = NULL, updated_at = :n WHERE id = :id"),
                   {"n": now, "id": str(o["endpoint_id"])})

    # 2) canal do proprio tenant: mesmo ID, ou o cadastro manual com o mesmo @usuario, ou novo
    ep = db.execute(text("""SELECT id FROM tenant_endpoints WHERE tenant_id = :t AND tipo_endpoint_id = :tipo AND ativo = TRUE
                            AND identificador_externo = :ig LIMIT 1"""), {"t": str(tenant_id), "tipo": str(tipo), "ig": ig_id}).scalar()
    if not ep and username:
        ep = db.execute(text("""SELECT id FROM tenant_endpoints WHERE tenant_id = :t AND tipo_endpoint_id = :tipo AND ativo = TRUE
                                AND identificador_externo IS NULL
                                AND lower(replace(coalesce(identificador_publico, ''), '@', '')) = lower(:u) LIMIT 1"""),
                        {"t": str(tenant_id), "tipo": str(tipo), "u": username}).scalar()
    if ep:
        db.execute(text("""UPDATE tenant_endpoints SET identificador_externo = :ig, identificador_publico = :u, updated_at = :n
                           WHERE id = :id"""), {"ig": ig_id, "u": username or None, "n": now, "id": str(ep)})
    else:
        base = (code_prefix + re.sub(r"[^A-Z0-9]", "_", (username or ig_id).upper()))[:90]
        # codigo unico no tenant: canais antigos (inativos, p.ex. apos um pedido de exclusao) continuam ocupando o codigo deles
        codigo, n = base, 1
        while db.execute(text("SELECT 1 FROM tenant_endpoints WHERE tenant_id = :t AND codigo = :c"), {"t": str(tenant_id), "c": codigo}).scalar():
            n += 1
            codigo = f"{base}_{ig_id[-4:]}" if n == 2 else f"{base}_{ig_id[-4:]}_{n - 1}"
        ep = db.execute(text("""INSERT INTO tenant_endpoints (tenant_id, codigo, nome, identificador_externo, identificador_publico, url, tipo_endpoint_id)
                                VALUES (:t, :c, :nome, :ig, :u, :url, :tipo) RETURNING id"""),
                        {"t": str(tenant_id), "c": codigo, "nome": display_name[:150], "ig": ig_id,
                         "u": username or None, "url": url, "tipo": str(tipo)}).scalar()

    # 3) conexao tecnica (1 por canal): token sempre criptografado
    escopos = sorted({p.strip() for p in permissions.split(",") if p.strip()})
    if app_user_id:
        meta = {**meta, "app_user_id": str(app_user_id)}
    expira = now + timedelta(seconds=expires_in) if expires_in else None
    renovar = now + timedelta(seconds=max(expires_in - 10 * 86400, 86400)) if expires_in else None
    db.execute(text("""
        INSERT INTO canal_conexoes (tenant_id, endpoint_id, tipo_conexao, status, escopos, token_tipo, token_enc, token_key_version,
               token_expira_em, renovar_em, webhook_assinado, webhook_campos, metadados, conectado_por_usuario_id, conectado_em)
        VALUES (:t, :ep, :tc, 'CONECTADO', CAST(:escopos AS jsonb), :tt, :enc, :kv,
                :exp, :renew, :sub, CAST(:campos AS jsonb), CAST(:meta AS jsonb), :uid, :now)
        ON CONFLICT (endpoint_id) DO UPDATE SET
            tipo_conexao = EXCLUDED.tipo_conexao, status = 'CONECTADO', escopos = EXCLUDED.escopos, token_tipo = EXCLUDED.token_tipo,
            token_enc = EXCLUDED.token_enc,
            token_key_version = EXCLUDED.token_key_version, token_expira_em = EXCLUDED.token_expira_em, renovar_em = EXCLUDED.renovar_em,
            webhook_assinado = EXCLUDED.webhook_assinado, webhook_campos = EXCLUDED.webhook_campos, metadados = EXCLUDED.metadados,
            conectado_por_usuario_id = EXCLUDED.conectado_por_usuario_id, conectado_em = EXCLUDED.conectado_em,
            desconectado_em = NULL, ultimo_erro = NULL, ultimo_erro_em = NULL, updated_at = :now
    """), {"t": str(tenant_id), "ep": str(ep), "tc": tipo_conexao, "tt": token_tipo, "escopos": json.dumps(escopos),
           "enc": meta_crypto.encrypt_token(token), "kv": meta_crypto.CURRENT_KEY_VERSION, "exp": expira, "renew": renovar,
           "sub": subscribed, "campos": json.dumps(webhook_fields if subscribed else []), "meta": json.dumps(meta),
           "uid": str(user_id), "now": now})
    if webhook_error:
        db.execute(text("UPDATE canal_conexoes SET ultimo_erro = :e, ultimo_erro_em = :n WHERE endpoint_id = :ep"),
                   {"e": f"webhook:{webhook_error}"[:200], "n": now, "ep": str(ep)})
    db.commit()
    return str(ep)


def revoke(db: Session, tenant_id, provider: str = "INSTAGRAM") -> bool:
    now = utcnow()
    n = db.execute(text("""
        UPDATE canal_conexoes c SET status = 'REVOGADO', token_enc = NULL, webhook_assinado = FALSE,
               desconectado_em = :n, updated_at = :n
          FROM tenant_endpoints e JOIN tipos_endpoint te ON te.id = e.tipo_endpoint_id
         WHERE c.endpoint_id = e.id AND e.tenant_id = :t AND te.codigo = :p AND c.status <> 'REVOGADO'
    """), {"n": now, "t": str(tenant_id), "p": provider}).rowcount
    db.commit()
    return n > 0


def revoke_endpoint(db: Session, endpoint_id) -> bool:
    """Revoga a conexao de UM canal (callbacks da Meta). Apaga o token; True se havia algo a revogar."""
    now = utcnow()
    n = db.execute(text("""
        UPDATE canal_conexoes SET status = 'REVOGADO', token_enc = NULL, webhook_assinado = FALSE,
               desconectado_em = :n, updated_at = :n
         WHERE endpoint_id = :ep AND status <> 'REVOGADO'
    """), {"n": now, "ep": str(endpoint_id)}).rowcount
    db.commit()
    return n > 0


def anonymize_endpoint(db: Session, endpoint_id) -> None:
    """Exclusao de dados: inativa o canal e remove nome, @usuario, URL e IDs da conta; limpa os metadados da conexao.

    O canal nao e apagado (outras tabelas podem referencia-lo); fica inativo e sem dados pessoais. Uma nova conexao da mesma
    conta cria um canal novo.
    """
    now = utcnow()
    db.execute(text("""
        UPDATE tenant_endpoints SET ativo = FALSE, nome = 'Removed channel', identificador_externo = NULL,
               identificador_publico = NULL, url = NULL, updated_at = :n WHERE id = :ep
    """), {"n": now, "ep": str(endpoint_id)})
    db.execute(text("UPDATE canal_conexoes SET metadados = '{}'::jsonb, escopos = '[]'::jsonb, updated_at = :n WHERE endpoint_id = :ep"),
               {"n": now, "ep": str(endpoint_id)})
    db.commit()


def get_credentials(db: Session, endpoint_id) -> dict | None:
    """Token em claro + IDs, somente para conexoes ativas. Nunca logar o resultado."""
    row = db.execute(text("""
        SELECT c.id AS conexao_id, c.token_enc, e.identificador_externo AS ig_id, c.metadados
          FROM canal_conexoes c JOIN tenant_endpoints e ON e.id = c.endpoint_id
         WHERE c.endpoint_id = :ep AND c.status IN ('CONECTADO','EXPIRANDO') AND c.token_enc IS NOT NULL
    """), {"ep": str(endpoint_id)}).mappings().first()
    if not row:
        return None
    return {"conexao_id": row["conexao_id"], "token": meta_crypto.decrypt_token(row["token_enc"]), "ig_id": row["ig_id"],
            "username": (row["metadados"] or {}).get("username")}


def resolve_by_external_id(db: Session, provider: str, external_id: str) -> dict | None:
    """Webhook: acha o tenant dono da conta (Instagram: ID da conta profissional; Facebook: ID da Pagina).
    So conexoes ativas e tenants ativos."""
    row = db.execute(text("""
        SELECT e.id AS endpoint_id, e.tenant_id
          FROM tenant_endpoints e
          JOIN tipos_endpoint te ON te.id = e.tipo_endpoint_id
          JOIN canal_conexoes c ON c.endpoint_id = e.id
          JOIN tenants t ON t.id = e.tenant_id
         WHERE te.codigo = :p AND e.identificador_externo = :ext AND e.ativo = TRUE AND t.ativo = TRUE
           AND c.status IN ('CONECTADO','EXPIRANDO')
         LIMIT 1
    """), {"p": provider, "ext": str(external_id)}).mappings().first()
    return dict(row) if row else None


def resolve_by_ig_id(db: Session, ig_id: str) -> dict | None:
    return resolve_by_external_id(db, "INSTAGRAM", ig_id)


def due_for_refresh(db: Session, now=None) -> list[dict]:
    rows = db.execute(text("""SELECT id AS conexao_id, token_enc FROM canal_conexoes
                              WHERE status IN ('CONECTADO','EXPIRANDO') AND token_enc IS NOT NULL AND renovar_em IS NOT NULL AND renovar_em <= :n"""),
                      {"n": now or utcnow()}).mappings().all()
    return [dict(r) for r in rows]


def mark_refreshed(db: Session, conexao_id, token: str, expires_in: int) -> None:
    now = utcnow()
    db.execute(text("""UPDATE canal_conexoes SET token_enc = :enc, token_key_version = :kv, token_expira_em = :exp, renovar_em = :renew,
                       status = 'CONECTADO', ultimo_erro = NULL, ultimo_erro_em = NULL, updated_at = :n WHERE id = :id"""),
               {"enc": meta_crypto.encrypt_token(token), "kv": meta_crypto.CURRENT_KEY_VERSION, "exp": now + timedelta(seconds=expires_in),
                "renew": now + timedelta(seconds=max(expires_in - 10 * 86400, 86400)), "n": now, "id": str(conexao_id)})
    db.commit()


def mark_error(db: Session, conexao_id, code: str, expired: bool) -> None:
    now = utcnow()
    db.execute(text("""UPDATE canal_conexoes SET ultimo_erro = :e, ultimo_erro_em = :n,
                       status = CASE WHEN :x THEN 'EXPIRADO' ELSE status END, updated_at = :n WHERE id = :id"""),
               {"e": f"refresh:{code}"[:200], "n": now, "x": expired, "id": str(conexao_id)})
    db.commit()
