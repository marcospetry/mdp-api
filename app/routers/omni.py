"""API da area Omni (Integrations, Inbox, Comments) para o tenant autenticado.

Todas as rotas exigem contexto de TENANT e permissao OMNI_* do perfil (perfis com acesso_total passam).
Dados de conversas e comentarios vivem no banco do tenant (omni_*); o status das conexoes vem da
plataforma (tenant_endpoints + canal_conexoes). Tokens NUNCA sao retornados.
"""
from __future__ import annotations

import hmac
import logging
import secrets
from datetime import timedelta
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import PlatformSessionLocal, get_platform_db
from app.security.dependencies import get_authorized_tenant_db, require_permission
from app.services import meta_instagram, omni_connections, omni_sync
from app.services.auth_service import utcnow
from app.services.omni_send import send_comment_reply, send_direct_message

logger = logging.getLogger("mdp.omni")

router = APIRouter(prefix="/api/omni", tags=["Omni"])

PROVIDERS = ("INSTAGRAM", "FACEBOOK")
CANAIS = ("INSTAGRAM", "FACEBOOK")
REPLY_WINDOW = timedelta(hours=24)
MAX_REPLY_CHARS = 1000


class ReplyIn(BaseModel):
    text: str


def _iso(value):
    return value.isoformat() if value else None


def _clean_text(value: str, max_bytes: int | None = None) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail="Message cannot be empty.")
    if len(cleaned) > MAX_REPLY_CHARS:
        raise HTTPException(status_code=422, detail=f"Message is too long (max {MAX_REPLY_CHARS} characters).")
    if max_bytes and len(cleaned.encode("utf-8")) > max_bytes:
        raise HTTPException(status_code=422, detail=f"Message is too long (max {max_bytes} bytes).")
    return cleaned


def _canal_filter(canal: str | None) -> str | None:
    if canal is None:
        return None
    canal = canal.upper()
    if canal not in CANAIS:
        raise HTTPException(status_code=422, detail="Unknown channel.")
    return canal


# --------------------------------------------------------------------------- Integrations
@router.get("/integrations")
def list_integrations(
    context=Depends(require_permission("OMNI_INTEGRACOES")),
    platform_db: Session = Depends(get_platform_db),
):
    rows = platform_db.execute(
        text(
            """
            SELECT te.codigo AS provider, e.nome, c.status, c.conectado_em, c.token_expira_em, c.metadados
              FROM tenant_endpoints e
              JOIN tipos_endpoint te ON te.id = e.tipo_endpoint_id
              LEFT JOIN canal_conexoes c ON c.endpoint_id = e.id
             WHERE e.tenant_id = :t AND e.ativo = TRUE AND te.codigo IN ('INSTAGRAM', 'FACEBOOK')
             ORDER BY e.created_at
            """
        ),
        {"t": str(context["tenant_id"])},
    ).mappings().all()
    by_provider = {}
    for row in rows:
        by_provider.setdefault(row["provider"], row)
    result = []
    for provider in PROVIDERS:
        row = by_provider.get(provider)
        meta = (row["metadados"] or {}) if row else {}
        result.append(
            {
                "provider": provider,
                "status": omni_connections.api_status(row["status"] if row else None, row["token_expira_em"] if row else None),
                "account_name": (meta.get("name") or (row["nome"] if row else None)),
                "handle": meta.get("username"),
                "connected_at": _iso(row["conectado_em"]) if row else None,
                "token_expires_at": _iso(row["token_expira_em"]) if row else None,
            }
        )
    return result


def _provider_or_404(provider: str) -> str:
    provider = provider.upper()
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown provider.")
    return provider


OAUTH_COOKIE = "omni_oauth_nonce"
OAUTH_COOKIE_PATH = "/api/omni/oauth"
STATE_TTL = 600


def _meta_ready() -> bool:
    return bool(settings.omni_meta_enabled and settings.instagram_app_id and settings.instagram_app_secret
                and settings.omni_connection_encryption_key and settings.omni_public_base_url)


def _redirect_uri() -> str:
    return settings.omni_public_base_url.rstrip("/") + "/api/omni/oauth/instagram/callback"


@router.post("/integrations/{provider}/connect")
def connect_integration(provider: str, context=Depends(require_permission("OMNI_INTEGRACOES"))):
    provider = _provider_or_404(provider)
    if provider != "INSTAGRAM" or not _meta_ready():
        raise HTTPException(status_code=501, detail="Connecting channels is not enabled yet.")
    nonce = secrets.token_urlsafe(24)
    state = jwt.encode(
        {"purpose": "ig_oauth", "tid": str(context["tenant_id"]), "uid": str(context["usuario"].id), "nonce": nonce,
         "exp": utcnow() + timedelta(seconds=STATE_TTL)}, settings.secret_key, algorithm=settings.jwt_algorithm)
    resp = JSONResponse({"authorization_url": meta_instagram.build_authorize_url(_redirect_uri(), state)})
    # o nonce prende o fluxo a ESTE navegador (protege contra conectar a conta de outra pessoa ao seu tenant)
    resp.set_cookie(OAUTH_COOKIE, nonce, max_age=STATE_TTL, httponly=True, samesite="lax", path=OAUTH_COOKIE_PATH,
                    secure=settings.omni_public_base_url.startswith("https://"))
    return resp


@router.get("/oauth/instagram/callback", include_in_schema=False)
def instagram_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    def back(result: str, key: str = "ig_error", extra: str = ""):
        resp = RedirectResponse(f"/omni?{key}={result}{extra}", status_code=303)
        resp.delete_cookie(OAUTH_COOKIE, path=OAUTH_COOKIE_PATH)
        return resp

    if not _meta_ready():
        return back("disabled")
    if error:
        return back("denied")
    try:
        claims = jwt.decode(state or "", settings.secret_key, algorithms=[settings.jwt_algorithm])
        if claims.get("purpose") != "ig_oauth":
            raise jwt.InvalidTokenError("purpose")
    except jwt.PyJWTError:
        return back("state")
    cookie = request.cookies.get(OAUTH_COOKIE) or ""
    if not cookie or not hmac.compare_digest(cookie.encode(), str(claims.get("nonce", "")).encode()):
        return back("state")
    if not code:
        return back("denied")
    try:
        short = meta_instagram.exchange_code(code, _redirect_uri())
        long_ = meta_instagram.to_long_lived(short["access_token"])
        me = meta_instagram.get_me(long_["access_token"])
    except meta_instagram.MetaApiError as exc:
        logger.warning("ig_oauth_falhou code=%s", exc.code)
        return back("exchange")
    if me["account_type"].lower() not in meta_instagram.PROFESSIONAL_TYPES:
        return back("not_professional")
    granted = {p for p in short["permissions"].split(",") if p}
    if granted and not set(meta_instagram.SCOPES) <= granted:
        # nomes de permissao nao sao segredo: registrar ajuda a diagnosticar diferencas de formato da Meta
        logger.warning("ig_oauth_permissoes_recebidas=%s", sorted(granted))
        return back("permissions")
    db = PlatformSessionLocal()
    try:
        subscribed, webhook_error = True, None
        try:
            meta_instagram.subscribe_webhooks(long_["access_token"], me["user_id"])
        except meta_instagram.MetaApiError as exc:
            subscribed, webhook_error = False, exc.code
        omni_connections.upsert_instagram_connection(
            db, tenant_id=claims["tid"], user_id=claims["uid"], me=me, long_token=long_["access_token"], expires_in=long_["expires_in"],
            permissions=short["permissions"] or ",".join(meta_instagram.SCOPES), subscribed=subscribed, webhook_error=webhook_error,
            app_user_id=short.get("user_id") or None)
    except omni_connections.AccountAlreadyConnected:
        return back("already_connected")
    except omni_connections.EndpointTypeMissing:
        return back("setup")
    finally:
        db.close()
    logger.info("ig_conectado tenant=%s ig_id=%s webhook=%s", claims["tid"], me["user_id"], "ok" if subscribed else "falhou")
    return back("connected", key="ig", extra="" if subscribed else "&ig_warn=webhook")


@router.delete("/integrations/{provider}")
def disconnect_integration(provider: str, context=Depends(require_permission("OMNI_INTEGRACOES")),
                           platform_db: Session = Depends(get_platform_db)):
    provider = _provider_or_404(provider)
    if provider != "INSTAGRAM":
        raise HTTPException(status_code=501, detail="Disconnecting channels is not enabled yet.")
    revoked = omni_connections.revoke(platform_db, context["tenant_id"], "INSTAGRAM")
    logger.info("ig_desconectado tenant=%s revogado=%s", context["tenant_id"], revoked)
    return {"disconnected": revoked}


# --------------------------------------------------------------------------- Inbox
def _conversation_dict(row, now):
    cliente_em = row["ultima_mensagem_cliente_em"]
    return {
        "id": str(row["id"]),
        "channel": row["canal"],
        "name": row["participante_nome"],
        "username": row["participante_usuario"],
        "unread": row["nao_lidas"],
        "last_message_at": _iso(row["ultima_mensagem_em"]),
        "last_text": row.get("ultima_texto"),
        "reply_window_open": bool(cliente_em and (now - cliente_em) < REPLY_WINDOW),
    }


@router.get("/conversations")
def list_conversations(
    channel: str | None = Query(default=None),
    context=Depends(require_permission("OMNI_INBOX")),
    db: Session = Depends(get_authorized_tenant_db),
):
    canal = _canal_filter(channel)
    rows = db.execute(
        text(
            """
            SELECT c.id, c.canal, c.participante_nome, c.participante_usuario, c.nao_lidas,
                   c.ultima_mensagem_em, c.ultima_mensagem_cliente_em,
                   (SELECT m.texto FROM omni_mensagens m WHERE m.conversa_id = c.id
                     ORDER BY m.ocorrida_em DESC LIMIT 1) AS ultima_texto
              FROM omni_conversas c
             WHERE (CAST(:canal AS text) IS NULL OR c.canal = :canal) AND c.status = 'ABERTA'
             ORDER BY c.ultima_mensagem_em DESC NULLS LAST
             LIMIT 100
            """
        ),
        {"canal": canal},
    ).mappings().all()
    now = utcnow()
    return [_conversation_dict(dict(r), now) for r in rows]


def _get_conversation(db: Session, conversation_id: UUID):
    row = db.execute(
        text(
            """
            SELECT id, canal, endpoint_id, participante_externo_id, participante_nome, participante_usuario,
                   nao_lidas, ultima_mensagem_em, ultima_mensagem_cliente_em
              FROM omni_conversas WHERE id = :id
            """
        ),
        {"id": str(conversation_id)},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return dict(row)


def _message_dict(row):
    return {
        "id": str(row["id"]),
        "direction": row["direcao"],
        "text": row["texto"],
        "status": row["status_envio"],
        "error": row["erro"],
        "at": _iso(row["ocorrida_em"]),
    }


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(
    conversation_id: UUID,
    context=Depends(require_permission("OMNI_INBOX")),
    db: Session = Depends(get_authorized_tenant_db),
):
    conv = _get_conversation(db, conversation_id)
    rows = db.execute(
        text(
            """
            SELECT id, direcao, texto, status_envio, erro, ocorrida_em
              FROM omni_mensagens WHERE conversa_id = :id ORDER BY ocorrida_em ASC
            """
        ),
        {"id": str(conversation_id)},
    ).mappings().all()
    db.execute(text("UPDATE omni_conversas SET nao_lidas = 0 WHERE id = :id"), {"id": str(conversation_id)})
    db.commit()
    now = utcnow()
    conv_out = _conversation_dict({**conv, "nao_lidas": 0, "ultima_texto": None}, now)
    return {"conversation": conv_out, "messages": [_message_dict(r) for r in rows]}


@router.post("/conversations/{conversation_id}/reply", status_code=201)
def reply_conversation(
    conversation_id: UUID,
    body: ReplyIn,
    context=Depends(require_permission("OMNI_INBOX")),
    db: Session = Depends(get_authorized_tenant_db),
):
    message = _clean_text(body.text, max_bytes=1000)
    conv = _get_conversation(db, conversation_id)
    now = utcnow()
    cliente_em = conv["ultima_mensagem_cliente_em"]
    if not cliente_em or (now - cliente_em) >= REPLY_WINDOW:
        raise HTTPException(status_code=409, detail="The 24-hour reply window is closed.")
    result = send_direct_message(
        canal=conv["canal"],
        endpoint_id=str(conv["endpoint_id"]),
        recipient_id=conv["participante_externo_id"],
        text=message,
    )
    msg_id = uuid4()
    db.execute(
        text(
            """
            INSERT INTO omni_mensagens
              (id, conversa_id, direcao, external_message_id, tipo, texto, status_envio, erro,
               enviado_por_usuario_id, ocorrida_em)
            VALUES (:id, :conv, 'SAIDA', :ext, 'TEXTO', :texto, :status, :erro, :user, :now)
            """
        ),
        {
            "id": str(msg_id), "conv": str(conversation_id), "ext": result.external_id, "texto": message,
            "status": "ENVIADA" if result.ok else "FALHA", "erro": result.error,
            "user": str(context["usuario"].id), "now": now,
        },
    )
    if result.ok:
        db.execute(
            text("UPDATE omni_conversas SET ultima_mensagem_em = :now, updated_at = :now WHERE id = :id"),
            {"now": now, "id": str(conversation_id)},
        )
    db.commit()
    return {
        "id": str(msg_id), "direction": "SAIDA", "text": message,
        "status": "ENVIADA" if result.ok else "FALHA", "error": result.error, "at": _iso(now),
    }


# --------------------------------------------------------------------------- Comments
@router.get("/comments")
def list_comments(
    channel: str | None = Query(default=None),
    context=Depends(require_permission("OMNI_COMENTARIOS")),
    db: Session = Depends(get_authorized_tenant_db),
):
    canal = _canal_filter(channel)
    rows = db.execute(
        text(
            """
            SELECT id, canal, external_comment_id, post_external_id, post_resumo, post_permalink,
                   autor_nome, autor_usuario, texto, respondido, ocorrido_em
              FROM omni_comentarios
             WHERE origem = 'EXTERNO' AND (CAST(:canal AS text) IS NULL OR canal = :canal)
             ORDER BY ocorrido_em DESC LIMIT 100
            """
        ),
        {"canal": canal},
    ).mappings().all()
    externals = [r["external_comment_id"] for r in rows]
    replies = {}
    if externals:
        reply_rows = db.execute(
            text(
                """
                SELECT id, parent_external_id, texto, status_envio, erro, ocorrido_em
                  FROM omni_comentarios
                 WHERE origem = 'PROPRIO' AND parent_external_id = ANY(:parents)
                 ORDER BY ocorrido_em ASC
                """
            ),
            {"parents": externals},
        ).mappings().all()
        for rr in reply_rows:
            replies.setdefault(rr["parent_external_id"], []).append(
                {"id": str(rr["id"]), "text": rr["texto"], "status": rr["status_envio"],
                 "error": rr["erro"], "at": _iso(rr["ocorrido_em"])}
            )
    return [
        {
            "id": str(r["id"]), "channel": r["canal"], "post": r["post_resumo"], "post_url": r["post_permalink"],
            "author_name": r["autor_nome"], "author_username": r["autor_usuario"], "text": r["texto"],
            "replied": r["respondido"], "at": _iso(r["ocorrido_em"]),
            "replies": replies.get(r["external_comment_id"], []),
        }
        for r in rows
    ]


@router.post("/comments/sync")
def sync_comments(context=Depends(require_permission("OMNI_COMENTARIOS")), db: Session = Depends(get_authorized_tenant_db),
                  platform_db: Session = Depends(get_platform_db)):
    if not _meta_ready():
        return {"new": 0, "skipped": True}
    return omni_sync.sync_instagram_comments(platform_db, db, context["tenant_id"])


@router.post("/comments/{comment_id}/reply", status_code=201)
def reply_comment(
    comment_id: UUID,
    body: ReplyIn,
    context=Depends(require_permission("OMNI_COMENTARIOS")),
    db: Session = Depends(get_authorized_tenant_db),
):
    message = _clean_text(body.text)
    orig = db.execute(
        text(
            """
            SELECT id, canal, endpoint_id, external_comment_id, post_external_id
              FROM omni_comentarios WHERE id = :id AND origem = 'EXTERNO'
            """
        ),
        {"id": str(comment_id)},
    ).mappings().first()
    if not orig:
        raise HTTPException(status_code=404, detail="Comment not found.")
    result = send_comment_reply(
        canal=orig["canal"], endpoint_id=str(orig["endpoint_id"]),
        comment_id=orig["external_comment_id"], text=message,
    )
    now = utcnow()
    reply_id = uuid4()
    db.execute(
        text(
            """
            INSERT INTO omni_comentarios
              (id, canal, endpoint_id, external_comment_id, parent_external_id, post_external_id, origem,
               texto, respondido, enviado_por_usuario_id, status_envio, erro, ocorrido_em)
            VALUES (:id, :canal, :ep, :ext, :parent, :post, 'PROPRIO', :texto, FALSE, :user, :status, :erro, :now)
            """
        ),
        {
            "id": str(reply_id), "canal": orig["canal"], "ep": str(orig["endpoint_id"]),
            "ext": result.external_id or f"local-{reply_id}", "parent": orig["external_comment_id"],
            "post": orig["post_external_id"], "texto": message, "user": str(context["usuario"].id),
            "status": "ENVIADA" if result.ok else "FALHA", "erro": result.error, "now": now,
        },
    )
    if result.ok:
        db.execute(text("UPDATE omni_comentarios SET respondido = TRUE WHERE id = :id"), {"id": str(comment_id)})
    db.commit()
    return {
        "id": str(reply_id), "text": message, "status": "ENVIADA" if result.ok else "FALHA",
        "error": result.error, "at": _iso(now),
    }
