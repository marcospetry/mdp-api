"""Webhook do Facebook (Messenger + feed da Pagina). Rotas: GET (verificacao) e POST (eventos) em /api/meta/facebook/webhook.

Seguranca: so funciona com OMNI_META_ENABLED; verifica o token na verificacao e a assinatura X-Hub-Signature-256 em cada evento
(segredo do app principal); nunca registra o conteudo das mensagens; responde 200 mesmo para eventos que nao interessam
(a Meta reenvia o que falha). O webhook do WhatsApp e o do Instagram (outras rotas) nao sao tocados.
"""
from __future__ import annotations

import hmac
import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import PlainTextResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import PlatformSessionLocal, tenant_session
from app.services import meta_facebook, omni_connections, omni_store

logger = logging.getLogger("mdp.meta.facebook.webhook")
router = APIRouter(prefix="/api/meta/facebook", tags=["Meta Facebook"])
MAX_BODY_BYTES = 1_000_000


def _enabled() -> None:
    if not (settings.omni_meta_enabled and settings.facebook_webhook_verify_token and meta_facebook.app_secret()):
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/webhook", include_in_schema=False)
def verify(hub_mode: str | None = Query(default=None, alias="hub.mode"),
           hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
           hub_verify_token: str | None = Query(default=None, alias="hub.verify_token")):
    _enabled()
    if (hub_mode == "subscribe" and hub_challenge is not None and hub_verify_token
            and hmac.compare_digest(hub_verify_token.encode(), settings.facebook_webhook_verify_token.encode())):
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/webhook", include_in_schema=False)
async def receive(request: Request):
    _enabled()
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")
    if not meta_facebook.verify_signature(raw, request.headers.get("x-hub-signature-256"), [meta_facebook.app_secret()]):
        raise HTTPException(status_code=403, detail="Invalid signature")
    try:
        body = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON") from None
    failed = await run_in_threadpool(process_payload, body)
    if failed:
        raise HTTPException(status_code=500, detail="Temporary failure")  # a Meta tenta de novo; a gravacao e idempotente
    return {"received": True}


def process_payload(body) -> bool:
    """Devolve True se algum evento falhou por erro de banco (para a Meta reenviar)."""
    failed = False
    platform_db = PlatformSessionLocal()
    try:
        for payload in body if isinstance(body, list) else [body]:
            if not isinstance(payload, dict) or payload.get("object") != "page":
                continue
            for entry in payload.get("entry") or []:
                try:
                    _handle_entry(platform_db, entry)
                except SQLAlchemyError:
                    logger.exception("fb_webhook_erro_banco")
                    failed = True
                except Exception as exc:  # noqa: BLE001 - evento malformado nao pode derrubar o lote
                    logger.warning("fb_webhook_evento_ignorado tipo=%s", exc.__class__.__name__)
    finally:
        platform_db.close()
    return failed


def _handle_entry(platform_db, entry: dict) -> None:
    page_id = str(entry.get("id") or "")
    target = omni_connections.resolve_by_external_id(platform_db, "FACEBOOK", page_id) if page_id else None
    if not target:
        logger.info("fb_webhook_pagina_desconhecida page_id=%s", page_id)
        return
    try:
        creds = omni_connections.get_credentials(platform_db, target["endpoint_id"])
    except RuntimeError:
        creds = None
    msgs = comments = 0
    with tenant_session(platform_db, target["tenant_id"]) as tdb:
        for ev in entry.get("messaging") or []:
            msgs += _handle_message(tdb, target["endpoint_id"], page_id, ev, creds)
        for ch in entry.get("changes") or []:
            if ch.get("field") == "feed":
                comments += _handle_feed(tdb, target["endpoint_id"], page_id, ch.get("value") or {}, creds)
    logger.info("fb_webhook page_id=%s mensagens=%d comentarios=%d", page_id, msgs, comments)


def _handle_message(tdb, endpoint_id, page_id: str, ev: dict, creds) -> int:
    msg = ev.get("message")
    if not isinstance(msg, dict):
        return 0  # leituras, entregas, postbacks: fora do escopo desta etapa
    sender = str((ev.get("sender") or {}).get("id") or "")
    if not sender or sender == page_id or msg.get("is_echo") or not msg.get("mid"):
        return 0  # eco = mensagem enviada pela propria Pagina
    text_body, attachments = msg.get("text"), msg.get("attachments")
    tipo = "TEXTO" if text_body else ("ANEXO" if attachments else "OUTRO")
    body = text_body or ("[attachment]" if attachments else "[unsupported message]")
    res = omni_store.store_incoming_dm(tdb, endpoint_id=endpoint_id, sender_id=sender, mid=str(msg["mid"]), body=body, tipo=tipo,
                                       ts=omni_store.to_datetime(ev.get("timestamp")), canal="FACEBOOK")
    if res["inserted"] and res["needs_profile"] and creds:
        try:
            prof = meta_facebook.get_user_profile(creds["token"], sender)
            omni_store.set_profile(tdb, res["conversa_id"], prof.get("name"), None)
        except Exception:  # noqa: BLE001 - o nome e opcional
            pass
    return 1 if res["inserted"] else 0


def _handle_feed(tdb, endpoint_id, page_id: str, value: dict, creds) -> int:
    """So comentarios novos (item=comment, verb=add). Posts, reacoes e edicoes sao ignorados."""
    if value.get("item") != "comment" or value.get("verb") != "add":
        return 0
    comment_id = str(value.get("comment_id") or "")
    author = value.get("from") or {}
    if not comment_id or str(author.get("id") or "") == page_id:
        return 0  # comentario da propria Pagina (nossas respostas)
    post_id = str(value.get("post_id") or "") or None
    parent_id = str(value.get("parent_id") or "") or None
    if parent_id and parent_id == post_id:
        parent_id = None  # comentario de primeiro nivel: o "pai" e o proprio post
    resumo = link = None
    if post_id:
        known = omni_store.known_post(tdb, endpoint_id, post_id)
        if known:
            resumo, link = known["post_resumo"], known["post_permalink"]
        elif creds:
            try:
                post = meta_facebook.get_post(creds["token"], post_id)
                resumo, link = post.get("message"), post.get("permalink_url")
            except Exception:  # noqa: BLE001
                pass
    return 1 if omni_store.store_comment(
        tdb, endpoint_id=endpoint_id, comment_id=comment_id, media_id=post_id, parent_id=parent_id, body=value.get("message"),
        author_id=author.get("id"), author_username=author.get("name"), ts=omni_store.to_datetime(value.get("created_time")),
        post_resumo=resumo, post_permalink=link, canal="FACEBOOK") else 0
