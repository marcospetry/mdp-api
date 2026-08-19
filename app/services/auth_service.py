from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from uuid import UUID
from sqlalchemy.orm import Session

from app.config import settings
from app.models.auth import SessaoUsuario, Usuario, UsuarioEmpresa
from app.models.empresa import Empresa
from app.security.jwt import create_access_token


def utcnow():
    return datetime.now(timezone.utc)


def normalize_refresh_token(token: str) -> str:
    return (token or "").strip()


def hash_refresh_token(token: str) -> str:
    return sha256(normalize_refresh_token(token).encode()).hexdigest()


def refresh_token_fingerprint(token: str) -> str:
    """Identificador seguro para log/diagnóstico. Nunca retorna o token puro."""
    return hash_refresh_token(token)[:12]


def resolve_empresa(db: Session, usuario: Usuario, empresa_id: UUID | None):
    vinculos = db.query(UsuarioEmpresa).filter(
        UsuarioEmpresa.usuario_id == usuario.id,
        UsuarioEmpresa.ativo.is_(True),
    ).all()

    if empresa_id:
        vinculo = next((v for v in vinculos if v.empresa_id == empresa_id), None)
        if vinculo:
            return empresa_id, vinculo

        # Superadmin pode atuar em outra empresa, mas somente se ela realmente existir e estiver ativa.
        if usuario.is_superadmin:
            empresa = db.query(Empresa).filter(
                Empresa.id == empresa_id,
                Empresa.ativo.is_(True),
            ).first()
            if empresa:
                return empresa_id, None

        return None, None

    if len(vinculos) == 1:
        return vinculos[0].empresa_id, vinculos[0]
    if len(vinculos) > 1:
        return None, "MULTIPLAS_EMPRESAS"
    return None, None


def create_session(
    db: Session,
    usuario: Usuario,
    empresa_id: UUID | None,
    ip: str | None,
    user_agent: str | None,
):
    refresh_token = secrets.token_urlsafe(48)
    sessao = SessaoUsuario(
        usuario_id=usuario.id,
        empresa_id=empresa_id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        expira_em=utcnow() + timedelta(days=settings.refresh_token_days),
        ip_origem=ip,
        user_agent=user_agent,
    )
    db.add(sessao)
    db.flush()
    access_token = create_access_token(usuario.id, sessao.id, empresa_id)
    return sessao, access_token, refresh_token


def rotate_refresh_session(db: Session, refresh_token: str):
    """
    Valida e rotaciona um refresh token.

    Retorno:
      (nova_sessao, access_token, novo_refresh_token, motivo_erro)

    motivo_erro:
      EMPTY | NOT_FOUND | REVOKED | EXPIRED | USER_INVALID | None
    """
    token = normalize_refresh_token(refresh_token)
    if not token:
        return None, None, None, "EMPTY"

    token_hash = hash_refresh_token(token)
    sessao = db.query(SessaoUsuario).filter(
        SessaoUsuario.refresh_token_hash == token_hash
    ).first()

    if not sessao:
        return None, None, None, "NOT_FOUND"

    now = utcnow()
    if sessao.revogada_em is not None:
        return None, None, None, "REVOKED"
    if sessao.expira_em <= now:
        return None, None, None, "EXPIRED"

    usuario = db.query(Usuario).filter(
        Usuario.id == sessao.usuario_id,
        Usuario.ativo.is_(True),
    ).first()
    if not usuario:
        return None, None, None, "USER_INVALID"

    sessao.revogada_em = now
    sessao.motivo_revogacao = "ROTACAO_REFRESH"

    nova_sessao, access_token, novo_refresh_token = create_session(
        db,
        usuario,
        sessao.empresa_id,
        str(sessao.ip_origem) if sessao.ip_origem else None,
        sessao.user_agent,
    )
    return nova_sessao, access_token, novo_refresh_token, None


def revoke_session(sessao: SessaoUsuario, motivo: str = "LOGOUT"):
    if sessao.revogada_em is None:
        sessao.revogada_em = utcnow()
        sessao.motivo_revogacao = motivo
    return sessao
