"""Filtros de log: mascaram parametros sensiveis de URL (codigo OAuth, tokens, segredos) antes de gravar."""
from __future__ import annotations

import logging
import re

_SENSITIVE = re.compile(r"([?&\s](?:code|state|access_token|client_secret|hub\.verify_token)=)[^&\s\"']+")


def redact(value: str) -> str:
    return _SENSITIVE.sub(r"\1REDACTED", value)


class RedactSecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = redact(record.msg)
            if isinstance(record.args, tuple):
                record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        except Exception:  # noqa: BLE001 - log nunca pode derrubar a requisicao
            pass
        return True


def install() -> None:
    """Chamado uma vez na subida do app. O httpx registra a URL completa (com access_token na query) em INFO: so WARNING."""
    for name in ("uvicorn.access", "httpx", "httpcore"):
        lg = logging.getLogger(name)
        if not any(isinstance(f, RedactSecretsFilter) for f in lg.filters):
            lg.addFilter(RedactSecretsFilter())
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
