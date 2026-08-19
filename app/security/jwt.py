from datetime import datetime, timedelta, timezone
from uuid import UUID
import jwt

from app.config import settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(usuario_id: UUID, sessao_id: UUID, empresa_id: UUID | None) -> str:
    now = _now()
    payload = {
        "sub": str(usuario_id),
        "sid": str(sessao_id),
        "empresa_id": str(empresa_id) if empresa_id else None,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_preauth_token(usuario_id: UUID, empresa_id: UUID | None, purpose: str) -> str:
    now = _now()
    payload = {
        "sub": str(usuario_id),
        "empresa_id": str(empresa_id) if empresa_id else None,
        "type": "preauth",
        "purpose": purpose,
        "iat": now,
        "exp": now + timedelta(minutes=settings.preauth_token_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str | None = None) -> dict:
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Tipo de token inválido")
    return payload
