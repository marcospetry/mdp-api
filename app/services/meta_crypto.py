"""Criptografia dos tokens das contas conectadas (Instagram/Facebook).

Usa uma chave PROPRIA (OMNI_CONNECTION_ENCRYPTION_KEY), diferente da do MFA, para poder girar uma sem afetar a outra.
O token nunca e gravado em claro, nunca e devolvido pela API e nunca vai para log.
"""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

CURRENT_KEY_VERSION = 1


def _fernet() -> Fernet:
    key = settings.omni_connection_encryption_key
    if not key:
        raise RuntimeError("OMNI_CONNECTION_ENCRYPTION_KEY nao configurada")
    return Fernet(key.encode())


def encrypt_token(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(token_enc: str) -> str:
    try:
        return _fernet().decrypt(token_enc.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Nao foi possivel descriptografar o token da conexao") from exc
