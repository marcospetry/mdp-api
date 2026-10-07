"""Envio de respostas do Omni para a Meta (Instagram e Messenger).

ETAPA ATUAL: o canal Meta AINDA NAO esta conectado, entao nada e enviado de verdade.
As funcoes abaixo sao o ponto unico de integracao: o patch do backend da Meta vai
implementa-las (chamada a Graph API com o token criptografado de canal_conexoes).
Enquanto isso, devolvem falha explicita para que a tela nunca mostre "enviado"
quando nada saiu.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SendResult:
    ok: bool
    external_id: str | None = None
    error: str | None = None


def send_direct_message(*, canal: str, endpoint_id: str, recipient_id: str, text: str) -> SendResult:
    return SendResult(ok=False, error="channel_not_connected")


def send_comment_reply(*, canal: str, endpoint_id: str, comment_id: str, text: str) -> SendResult:
    return SendResult(ok=False, error="channel_not_connected")
