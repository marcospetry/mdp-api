"""Webhook do Instagram (Business Login for Instagram). Rotas: GET (verificacao) e POST (eventos) em /api/meta/instagram/webhook.

Seguranca: so funciona com OMNI_META_ENABLED; verifica o token na verificacao e a assinatura X-Hub-Signature-256 em cada evento;
nunca registra o conteudo das mensagens; responde 200 mesmo para eventos que nao interessam (a Meta reenvia o que falha).
O webhook do WhatsApp (outra rota, outro produto) nao e tocado.
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
from app.services import meta_instagram, omni_connections, omni_store

logger = logging.getLogger("mdp.meta.instagram.webhook")
router = APIRouter(prefix="/api/meta/instagram", tags=["Meta Instagram"])
MAX_BODY_BYTES = 1_000_000


def _enabled() -> None:
    if not (settings.omni_meta_enabled and settings.instagram_webhook_verify_token and settings.instagram_app_secret):
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/webhook", include_in_schema=False)
def verify(hub_mode: str | None = Query(default=None, alias="hub.mode"),
           hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
           hub_verify_token: str | None = Query(default=None, alias="hub.verify_token")):
    _enabled()
    if (hub_mode == "subscribe" and hub_challenge is not None and hub_verify_token
            and hmac.compare_digest(hub_verify_token.encode(), settings.instagram_webhook_verify_token.encode())):
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/webhook", include_in_schema=False)
async def receive(request: Request):
    _enabled()
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")
    # o segredo do app do Instagram assina os eventos; aceitamos tambem o do app principal por seguranca de compatibilidade
    secrets_ok = [settings.instagram_app_secret, settings.meta_whatsapp_app_secret]
    if not meta_instagram.verify_signature(raw, request.headers.get("x-hub-signature-256"), secrets_ok):
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
            if not isinstance(payload, dict) or payload.get("object") != "instagram":
                continue
            for entry in payload.get("entry") or []:
                try:
                    _handle_entry(platform_db, entry)
                except SQLAlchemyError:
                    logger.exception("ig_webhook_erro_banco")
                    failed = True
                except Exception as exc:  # noqa: BLE001 - evento malformado nao pode derrubar o lote
                    logger.warning("ig_webhook_evento_ignorado tipo=%s", exc.__class__.__name__)
    finally:
        platform_db.close()
    return failed


def _handle_entry(platform_db, entry: dict) -> None:
    ig_id = str(entry.get("id") or "")
    target = omni_connections.resolve_by_ig_id(platform_db, ig_id) if ig_id else None
    if not target:
        logger.info("ig_webhook_conta_desconhecida ig_id=%s", ig_id)
        return
    try:
        creds = omni_connections.get_credentials(platform_db, target["endpoint_id"])
    except RuntimeError:
        creds = None
    msgs = comments = 0
    with tenant_session(platform_db, target["tenant_id"]) as tdb:
        for ev in entry.get("messaging") or []:
            msgs += _handle_message(tdb, target["endpoint_id"], ig_id, ev, creds)
        changes = entry.get("changes") or ([{"field": entry["field"], "value": entry.get("value") or {}}] if entry.get("field") else [])
        for ch in changes:
            if ch.get("field") in ("comments", "live_comments"):
                comments += _handle_comment(tdb, target["endpoint_id"], ig_id, ch.get("value") or {}, creds)
    logger.info("ig_webhook ig_id=%s mensagens=%d comentarios=%d", ig_id, msgs, comments)


def _handle_message(tdb, endpoint_id, ig_id: str, ev: dict, creds) -> int:
    msg = ev.get("message")
    if not isinstance(msg, dict):
        return 0  # reacoes, leituras, postbacks: fora do escopo desta etapa
    sender = str((ev.get("sender") or {}).get("id") or "")
    if not sender or sender == ig_id or msg.get("is_echo") or msg.get("is_self") or msg.get("is_deleted") or not msg.get("mid"):
        return 0
    text_body, attachments = msg.get("text"), msg.get("attachments")
    tipo = "TEXTO" if text_body else ("ANEXO" if attachments else "OUTRO")
    body = text_body or ("[attachment]" if attachments else "[unsupported message]")
    res = omni_store.store_incoming_dm(tdb, endpoint_id=endpoint_id, sender_id=sender, mid=str(msg["mid"]), body=body, tipo=tipo,
                                       ts=omni_store.to_datetime(ev.get("timestamp")))
    if res["inserted"] and res["needs_profile"] and creds:
        try:
            prof = meta_instagram.get_user_profile(creds["token"], sender)
            omni_store.set_profile(tdb, res["conversa_id"], prof.get("name"), prof.get("username"))
        except Exception:  # noqa: BLE001 - o nome e opcional
            pass
    return 1 if res["inserted"] else 0


def _handle_comment(tdb, endpoint_id, ig_id: str, value: dict, creds) -> int:
    comment_id = str(value.get("id") or value.get("comment_id") or "")
    author = value.get("from") or {}
    username = author.get("username")
    own = ((creds or {}).get("username") or "").lower()
    if not comment_id or str(author.get("id") or "") == ig_id or (own and str(username or "").lower() == own):
        return 0  # comentario da propria conta (nossas respostas)
    media_id = str((value.get("media") or {}).get("id") or "") or None
    resumo = link = None
    if media_id:
        known = omni_store.known_post(tdb, endpoint_id, media_id)
        if known:
            resumo, link = known["post_resumo"], known["post_permalink"]
        elif creds:
            try:
                m = meta_instagram.get_media(creds["token"], media_id)
                resumo, link = m.get("caption"), m.get("permalink")
            except Exception:  # noqa: BLE001
                pass
    return 1 if omni_store.store_comment(
        tdb, endpoint_id=endpoint_id, comment_id=comment_id, media_id=media_id, parent_id=value.get("parent_id"), body=value.get("text"),
        author_id=author.get("id"), author_username=username, ts=omni_store.to_datetime(value.get("time") or None),
        post_resumo=resumo, post_permalink=link) else 0
