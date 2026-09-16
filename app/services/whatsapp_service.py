"""
Envio de mensagens de texto via WhatsApp Cloud API, usando o Phone Number ID
e o access token de sistema (SYSTEM_USER, sem expiração) já validados na
sessão de coexistência.
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger("whatsapp_service")

GRAPH_API_VERSION = "v23.0"


def enviar_mensagem_texto(numero_destino: str, texto: str) -> dict:
    """
    numero_destino: formato internacional com "+", ex: "+5541997905000".
    Não pode ser o próprio número comercial da MDP (a API rejeita).
    """
    url = (
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/"
        f"{settings.meta_whatsapp_phone_number_id}/messages"
    )
    headers = {
        "Authorization": f"Bearer {settings.meta_whatsapp_access_token}",
        "Content-Type": "application/json",
    }
    body = {
        "messaging_product": "whatsapp",
        "to": numero_destino,
        "type": "text",
        "text": {"body": texto},
    }

    with httpx.Client(timeout=15) as client:
        resposta = client.post(url, headers=headers, json=body)

    if resposta.status_code >= 400:
        logger.error("Falha ao enviar mensagem: %s", resposta.text)
        resposta.raise_for_status()

    return resposta.json()
