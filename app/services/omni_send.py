"""Envio de respostas do Omni para a Meta (Instagram). O Facebook/Messenger ainda nao esta conectado.

As funcoes devolvem SendResult: nunca levantam erro e nunca marcam como enviado o que nao saiu.
Codigos de erro curtos e seguros (sem texto da Meta): channel_not_connected, meta_<codigo>, meta_unavailable.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import settings
from app.database import PlatformSessionLocal
from app.services import meta_instagram, omni_connections

logger = logging.getLogger("mdp.omni.send")


@dataclass
class SendResult:
    ok: bool
    external_id: str | None = None
    error: str | None = None


def _credentials(canal: str, endpoint_id: str):
    if canal != "INSTAGRAM" or not settings.omni_meta_enabled:
        return None
    db = PlatformSessionLocal()
    try:
        return omni_connections.get_credentials(db, endpoint_id)
    except RuntimeError:
        return None
    finally:
        db.close()


def _failure(exc: Exception) -> SendResult:
    if isinstance(exc, meta_instagram.MetaApiError):
        logger.warning("envio_meta_falhou code=%s status=%s", exc.code, exc.status)
        return SendResult(ok=False, error="meta_unavailable" if exc.code == "network" else f"meta_{exc.code}")
    logger.warning("envio_falhou tipo=%s", exc.__class__.__name__)
    return SendResult(ok=False, error="meta_unavailable")


def send_direct_message(*, canal: str, endpoint_id: str, recipient_id: str, text: str) -> SendResult:
    creds = _credentials(canal, endpoint_id)
    if not creds:
        return SendResult(ok=False, error="channel_not_connected")
    try:
        resp = meta_instagram.send_text(creds["token"], creds["ig_id"], recipient_id, text)
        return SendResult(ok=True, external_id=resp.get("message_id"))
    except Exception as exc:  # noqa: BLE001 - qualquer falha vira resultado, nunca erro 500 na tela
        return _failure(exc)


def send_comment_reply(*, canal: str, endpoint_id: str, comment_id: str, text: str) -> SendResult:
    creds = _credentials(canal, endpoint_id)
    if not creds:
        return SendResult(ok=False, error="channel_not_connected")
    try:
        resp = meta_instagram.reply_comment(creds["token"], comment_id, text)
        return SendResult(ok=True, external_id=resp.get("id"))
    except Exception as exc:  # noqa: BLE001
        return _failure(exc)
