"""
Webhook do WhatsApp (Cloud API / Coexistência) para o MDP Omni.

Duas responsabilidades:
1) GET  /api/whatsapp/webhook  -> verificação de assinatura exigida pela Meta
   na hora de configurar a Callback URL no App Dashboard.
2) POST /api/whatsapp/webhook  -> recebe os eventos reais (mensagens recebidas,
   ecos de mensagens enviadas manualmente pelo app do celular, status de
   entrega, etc). Por enquanto só loga e responde 200 rápido — persistência
   em banco fica para uma etapa seguinte.

Importante sobre coexistência: além do evento normal "messages" (mensagem que
um usuário do WhatsApp mandou para o número da MDP), a Meta também manda um
evento "message_echo" quando uma mensagem é enviada MANUALMENTE pelo
WhatsApp Business App no celular — isso é o que permite ao backend saber que
uma conversa já foi respondida por fora da API.
"""

import hashlib
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response

from app.config import settings

logger = logging.getLogger("whatsapp_webhook")

router = APIRouter(
    prefix="/api/whatsapp",
    tags=["WhatsApp Webhook"],
)


@router.get("/webhook")
def verificar_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
):
    """
    A Meta chama esse GET uma única vez, no momento em que você clica em
    "Verificar e salvar" na tela de configuração do webhook do App Dashboard.
    Ela manda o token que você digitou lá (hub_verify_token) e espera receber
    de volta exatamente o valor de hub_challenge, em texto puro, para
    confirmar que o endpoint é seu.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_whatsapp_verify_token:
        logger.info("Webhook verificado com sucesso pela Meta.")
        return Response(content=hub_challenge, media_type="text/plain")

    logger.warning("Falha na verificação do webhook: token não confere.")
    raise HTTPException(status_code=403, detail="Verify token inválido.")


def _assinatura_valida(corpo_bruto: bytes, assinatura_header: str | None) -> bool:
    """
    Confere o header X-Hub-Signature-256 que a Meta manda em todo POST,
    calculado como HMAC-SHA256 do corpo bruto da requisição usando o
    App Secret. Protege contra chamadas falsas para esse endpoint.
    """
    if not assinatura_header or not assinatura_header.startswith("sha256="):
        return False

    assinatura_recebida = assinatura_header.removeprefix("sha256=")
    assinatura_calculada = hmac.new(
        key=settings.meta_whatsapp_app_secret.encode("utf-8"),
        msg=corpo_bruto,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(assinatura_recebida, assinatura_calculada)


@router.post("/webhook")
async def receber_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
):
    corpo_bruto = await request.body()

    if not _assinatura_valida(corpo_bruto, x_hub_signature_256):
        logger.warning("Webhook recebido com assinatura inválida — ignorado.")
        # Responde 200 mesmo assim: a Meta reenvia/desabilita o webhook se
        # receber muitos erros, e uma assinatura inválida não deve contar
        # como "seu endpoint está com problema".
        return Response(status_code=200)

    payload = await request.json()
    logger.info("Webhook recebido: %s", payload)

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            valor = change.get("value", {})
            campo = change.get("field")

            mensagens = valor.get("messages", [])
            for msg in mensagens:
                logger.info(
                    "Mensagem recebida de %s (tipo=%s, id=%s): %s",
                    msg.get("from"),
                    msg.get("type"),
                    msg.get("id"),
                    msg.get("text", {}).get("body") if msg.get("type") == "text" else msg,
                )
                # TODO: persistir em banco (tabela de interações/conversas)
                # TODO: disparar para a fila/roteamento de resposta (n8n etc.)

            ecos = valor.get("message_echoes", [])
            for eco in ecos:
                logger.info(
                    "Eco de mensagem enviada manualmente pelo app do celular: %s",
                    eco,
                )
                # TODO: registrar como "respondido fora da API" na conversa

            statuses = valor.get("statuses", [])
            for status_evento in statuses:
                logger.info(
                    "Status de entrega: id=%s status=%s",
                    status_evento.get("id"),
                    status_evento.get("status"),
                )

            if campo and campo not in ("messages",):
                logger.info("Campo de webhook não tratado ainda: %s -> %s", campo, valor)

    return Response(status_code=200)
