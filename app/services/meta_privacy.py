"""Callbacks de privacidade da Meta: desautorizacao e exclusao de dados (Instagram e Facebook).

A Meta faz POST (application/x-www-form-urlencoded) com o campo `signed_request` = <assinatura>.<payload>, ambos em base64url.
A assinatura e HMAC-SHA256 do texto do payload com o segredo do app; o payload traz `user_id` (ID do usuario NO APP).

Este modulo nunca registra tokens, segredos nem conteudo de mensagens.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import secrets
from email import policy as email_policy
from email.parser import BytesParser
from urllib.parse import parse_qs

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.services import omni_connections, omni_store
from app.services.auth_service import utcnow

CODE_RE = re.compile(r"^[A-Z0-9]{16}$")
PROVIDERS = ("INSTAGRAM", "FACEBOOK")


def app_secrets() -> list[str]:
    """Segredos que podem assinar os pedidos: app do Instagram e app principal (mesma regra do webhook)."""
    return [s for s in (settings.instagram_app_secret, settings.meta_whatsapp_app_secret,
                        getattr(settings, "facebook_app_secret", None)) if s and s != "change-me"]


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def extract_signed_request(raw_body: bytes, content_type: str | None = None) -> str | None:
    """Le o campo signed_request do corpo, sem depender de python-multipart.

    A Meta ja enviou o callback de desautorizacao como multipart/form-data e o de exclusao como form-urlencoded;
    por isso os dois formatos sao aceitos (decidido pelo Content-Type; sem ele, tenta urlencoded).
    """
    if content_type and content_type.lower().lstrip().startswith("multipart/form-data"):
        return _extract_multipart(raw_body, content_type)
    try:
        fields = parse_qs(raw_body.decode("utf-8", errors="strict"), keep_blank_values=False)
    except UnicodeDecodeError:
        return None
    values = fields.get("signed_request")
    return values[0] if values else None


def _extract_multipart(raw_body: bytes, content_type: str) -> str | None:
    try:
        msg = BytesParser(policy=email_policy.HTTP).parsebytes(b"Content-Type: " + content_type.encode("latin-1", "ignore") + b"\r\n\r\n" + raw_body)
        if not msg.is_multipart():
            return None
        for part in msg.iter_parts():
            if part.get_param("name", header="content-disposition") == "signed_request" and not part.get_filename():
                value = part.get_payload(decode=True)
                text_value = value.decode("utf-8", errors="strict").strip() if value else ""
                return text_value or None
    except (ValueError, UnicodeError, LookupError):
        return None
    return None


def parse_signed_request(signed_request: str | None, secrets_list: list[str]) -> dict | None:
    """Devolve o payload se a assinatura confere com algum segredo; senao None. Nunca levanta por entrada malformada."""
    if not signed_request or signed_request.count(".") != 1:
        return None
    sig_part, payload_part = signed_request.split(".", 1)
    try:
        received = _b64url_decode(sig_part)
        payload = json.loads(_b64url_decode(payload_part))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get("algorithm", "")).upper() != "HMAC-SHA256":
        return None
    for secret in secrets_list:
        expected = hmac.new(secret.encode(), payload_part.encode(), hashlib.sha256).digest()
        if hmac.compare_digest(expected, received):
            user_id = str(payload.get("user_id") or "").strip()
            if not user_id or len(user_id) > 255:
                return None
            return {**payload, "user_id": user_id}
    return None


def diagnose_signed_request(signed_request: str | None, secrets_list: list[str]) -> dict:
    """Motivo (curto e seguro) pelo qual um signed_request foi recusado. So devolve NOMES de campos, nunca valores nem segredos.

    Nao altera a regra de aceite: serve apenas para o log quando a Meta chama e recebemos 403.
    """
    if not signed_request:
        return {"motivo": "sem_campo"}
    if signed_request.count(".") != 1:
        return {"motivo": "formato", "partes": signed_request.count(".") + 1}
    sig_part, payload_part = signed_request.split(".", 1)
    try:
        received = _b64url_decode(sig_part)
        payload = json.loads(_b64url_decode(payload_part))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return {"motivo": "base64_ou_json"}
    if not isinstance(payload, dict):
        return {"motivo": "payload_nao_objeto"}
    info = {"chaves": sorted(str(k) for k in payload)[:12], "algoritmo": str(payload.get("algorithm"))[:20],
            "assinatura_bytes": len(received), "segredos": len(secrets_list)}
    if str(payload.get("algorithm", "")).upper() != "HMAC-SHA256":
        return {"motivo": "algoritmo", **info}
    if not str(payload.get("user_id") or "").strip():
        return {"motivo": "sem_user_id", **info}
    for secret in secrets_list:
        if hmac.compare_digest(hmac.new(secret.encode(), payload_part.encode(), hashlib.sha256).digest(), received):
            return {"motivo": "ok", **info}
    return {"motivo": "assinatura", **info}


def find_channels(db: Session, meta_user_id: str) -> list[dict]:
    """Canais ativos (qualquer status de conexao) ligados a este user_id da Meta.

    Casa por DOIS IDs, porque nao ha confirmacao de qual a Meta envia: o ID do usuario no app gravado na conexao
    (metadados.app_user_id) ou o ID da conta que roteia webhooks (tenant_endpoints.identificador_externo).
    """
    rows = db.execute(text("""
        SELECT e.id AS endpoint_id, e.tenant_id, te.codigo AS provider, c.id AS conexao_id, c.status
          FROM tenant_endpoints e
          JOIN tipos_endpoint te ON te.id = e.tipo_endpoint_id
          LEFT JOIN canal_conexoes c ON c.endpoint_id = e.id
         WHERE e.ativo = TRUE AND te.codigo IN ('INSTAGRAM', 'FACEBOOK')
           AND (e.identificador_externo = :u OR c.metadados ->> 'app_user_id' = :u)
    """), {"u": meta_user_id}).mappings().all()
    return [dict(r) for r in rows]


def new_code() -> str:
    return secrets.token_hex(8).upper()  # 16 caracteres, so letras maiusculas e numeros


def record_request(db: Session, *, tipo: str, meta_user_id: str, status: str = "RECEBIDO", canais: int = 0, tenant_id=None) -> str:
    code = new_code()
    db.execute(text("""
        INSERT INTO meta_pedidos_privacidade (codigo, tipo, meta_user_id, status, canais_afetados, tenant_id, concluido_em)
        VALUES (:c, :t, :u, :s, :n, :tid, :done)
    """), {"c": code, "t": tipo, "u": meta_user_id, "s": status, "n": canais,
           "tid": str(tenant_id) if tenant_id else None, "done": None if status == "RECEBIDO" else utcnow()})
    db.commit()
    return code


def complete_request(db: Session, code: str, status: str, canais: int) -> None:
    db.execute(text("""UPDATE meta_pedidos_privacidade SET status = :s, canais_afetados = :n, concluido_em = :now WHERE codigo = :c"""),
               {"s": status, "n": canais, "now": utcnow(), "c": code})
    db.commit()


def get_request_status(db: Session, code: str) -> dict | None:
    if not CODE_RE.match(code or ""):
        return None
    row = db.execute(text("""SELECT tipo, status, created_at, concluido_em FROM meta_pedidos_privacidade WHERE codigo = :c"""),
                     {"c": code}).mappings().first()
    return dict(row) if row else None


def handle_deauthorization(db: Session, meta_user_id: str) -> dict:
    """O usuario removeu o app: revoga as conexoes (apaga o token). O conteudo ja gravado so sai no pedido de exclusao."""
    channels = find_channels(db, meta_user_id)
    revoked = 0
    for ch in channels:
        if omni_connections.revoke_endpoint(db, ch["endpoint_id"]):
            revoked += 1
    tenant_id = channels[0]["tenant_id"] if channels else None
    code = record_request(db, tipo="DESAUTORIZACAO", meta_user_id=meta_user_id, status="CONCLUIDO" if channels else "SEM_CORRESPONDENCIA",
                          canais=revoked, tenant_id=tenant_id)
    return {"code": code, "channels": len(channels), "revoked": revoked}


def handle_data_deletion(db: Session, meta_user_id: str, tenant_db_factory) -> dict:
    """Exclusao: revoga a conexao, apaga conversas/mensagens/comentarios do canal no banco do tenant e anonimiza o cadastro do canal.

    `tenant_db_factory(tenant_id)` e um context manager que abre a sessao do banco do tenant (tenant_session ja ligada ao db).
    O pedido e gravado ANTES, para que o codigo devolvido a Meta sempre exista na pagina de status.
    """
    channels = find_channels(db, meta_user_id)
    tenant_id = channels[0]["tenant_id"] if channels else None
    code = record_request(db, tipo="EXCLUSAO", meta_user_id=meta_user_id,
                          status="RECEBIDO" if channels else "SEM_CORRESPONDENCIA", canais=0, tenant_id=tenant_id)
    if not channels:
        return {"code": code, "channels": 0, "deleted": 0}
    done = 0
    for ch in channels:
        omni_connections.revoke_endpoint(db, ch["endpoint_id"])
        with tenant_db_factory(ch["tenant_id"]) as tdb:
            omni_store.delete_endpoint_data(tdb, ch["endpoint_id"])
        omni_connections.anonymize_endpoint(db, ch["endpoint_id"])
        done += 1
    complete_request(db, code, "CONCLUIDO", done)
    return {"code": code, "channels": len(channels), "deleted": done}
