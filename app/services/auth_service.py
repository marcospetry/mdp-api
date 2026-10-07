from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.database import tenant_session
from app.models.auth import UsuarioEmpresa, UsuarioTenantLocal
from app.models.empresa import Empresa
from app.models.platform_auth import PlatformSessaoUsuario, PlatformTenant, PlatformUsuario, PlatformUsuarioTenant
from app.security.jwt import create_access_token


def utcnow():
    return datetime.now(timezone.utc)


def acesso_expirado(usuario: PlatformUsuario, now: datetime | None = None) -> bool:
    """True se o usuario tem validade de acesso (acesso_expira_em) e ela ja venceu."""
    return bool(usuario.acesso_expira_em and usuario.acesso_expira_em <= (now or utcnow()))


def mfa_dispensa_valida(usuario: PlatformUsuario, now: datetime | None = None) -> bool:
    """Excecao de MFA (ex.: usuario de App Review da Meta). Nunca vale para SUPERADMIN,
    exige validade futura e so existe para quem nao tem MFA habilitado."""
    now = now or utcnow()
    return bool(
        usuario.mfa_dispensado
        and not usuario.is_superadmin
        and not usuario.mfa_habilitado
        and usuario.acesso_expira_em
        and usuario.acesso_expira_em > now
    )


def normalize_refresh_token(token: str) -> str:
    return (token or "").strip()


def hash_refresh_token(token: str) -> str:
    return sha256(normalize_refresh_token(token).encode()).hexdigest()


def refresh_token_fingerprint(token: str) -> str:
    return hash_refresh_token(token)[:12]


def resolve_tenant(db: Session, usuario: PlatformUsuario, tenant_id: UUID | None = None):
    q = db.query(PlatformUsuarioTenant).join(
        PlatformTenant, PlatformTenant.id == PlatformUsuarioTenant.tenant_id
    ).filter(
        PlatformUsuarioTenant.usuario_id == usuario.id,
        PlatformUsuarioTenant.ativo.is_(True),
        PlatformTenant.ativo.is_(True),
    )
    vinculos = q.all()
    if tenant_id:
        vinculo = next((v for v in vinculos if v.tenant_id == tenant_id), None)
        return (tenant_id, vinculo) if vinculo else (None, None)
    if len(vinculos) == 1:
        return vinculos[0].tenant_id, vinculos[0]
    if len(vinculos) > 1:
        return None, "MULTIPLOS_TENANTS"
    return None, None


def resolve_empresa_tenant(db: Session, platform_usuario_id: UUID):
    local = db.query(UsuarioTenantLocal).filter(
        UsuarioTenantLocal.platform_usuario_id == platform_usuario_id,
        UsuarioTenantLocal.ativo.is_(True),
    ).first()
    if not local:
        return None, None, None
    vinculos = db.query(UsuarioEmpresa).filter(
        UsuarioEmpresa.usuario_id == local.id,
        UsuarioEmpresa.ativo.is_(True),
    ).all()
    if len(vinculos) == 1:
        empresa = db.query(Empresa).filter(
            Empresa.id == vinculos[0].empresa_id,
            Empresa.ativo.is_(True),
        ).first()
        return (empresa.id if empresa else None), vinculos[0], local
    return None, None, local


def create_session(platform_db: Session, usuario: PlatformUsuario, tenant_id: UUID | None, empresa_id: UUID | None, ip: str | None, user_agent: str | None):
    refresh_token = secrets.token_urlsafe(48)
    sessao = PlatformSessaoUsuario(
        usuario_id=usuario.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        expira_em=utcnow() + timedelta(days=settings.refresh_token_days),
        ip_origem=ip,
        user_agent=user_agent,
        contexto_tipo="TENANT" if tenant_id else "PLATAFORMA",
        tenant_id=tenant_id,
        empresa_id=empresa_id,
    )
    platform_db.add(sessao)
    platform_db.flush()
    access_token = create_access_token(usuario.id, sessao.id, tenant_id, empresa_id)
    return sessao, access_token, refresh_token


def rotate_refresh_session(platform_db: Session, refresh_token: str):
    token = normalize_refresh_token(refresh_token)
    if not token:
        return None, None, None, "EMPTY"
    sessao = platform_db.query(PlatformSessaoUsuario).filter(
        PlatformSessaoUsuario.refresh_token_hash == hash_refresh_token(token)
    ).first()
    if not sessao:
        return None, None, None, "NOT_FOUND"
    now = utcnow()
    if sessao.revogada_em is not None:
        return None, None, None, "REVOKED"
    if sessao.expira_em <= now:
        return None, None, None, "EXPIRED"
    usuario = platform_db.query(PlatformUsuario).filter(
        PlatformUsuario.id == sessao.usuario_id,
        PlatformUsuario.ativo.is_(True),
    ).first()
    if not usuario:
        return None, None, None, "USER_INVALID"
    if acesso_expirado(usuario, now):
        return None, None, None, "ACCESS_EXPIRED"
    if sessao.contexto_tipo == "PLATAFORMA":
        if not usuario.is_superadmin:
            return None, None, None, "PLATFORM_ACCESS_REVOKED"
        tenant_id, empresa_id = None, None
    elif sessao.contexto_tipo == "TENANT":
        tenant_id = sessao.tenant_id
        if not tenant_id or not resolve_tenant(platform_db, usuario, tenant_id)[1]:
            return None, None, None, "TENANT_INVALID"
        with tenant_session(platform_db, tenant_id) as tenant_db:
            empresa_id, _, local = resolve_empresa_tenant(tenant_db, usuario.id)
        if not local:
            return None, None, None, "TENANT_USER_INVALID"
        # Empresa selecionada precisa continuar autorizada.
        if sessao.empresa_id and empresa_id != sessao.empresa_id:
            return None, None, None, "EMPRESA_CHANGED"
        empresa_id = sessao.empresa_id
    else:
        # Compatibilidade com sessoes anteriores a migration: somente tenant unico.
        tenant_id, vinculo = resolve_tenant(platform_db, usuario)
        if not tenant_id or vinculo == "MULTIPLOS_TENANTS":
            return None, None, None, "TENANT_INVALID"
        with tenant_session(platform_db, tenant_id) as tenant_db:
            empresa_id, _, local = resolve_empresa_tenant(tenant_db, usuario.id)
        if not local:
            return None, None, None, "TENANT_USER_INVALID"
    sessao.revogada_em = now
    sessao.motivo_revogacao = "ROTACAO_REFRESH"
    nova, access, novo_refresh = create_session(platform_db, usuario, tenant_id, empresa_id, sessao.ip_origem, sessao.user_agent)
    sessao.ultimo_uso_em = now
    return nova, access, novo_refresh, None


def revoke_session(sessao: PlatformSessaoUsuario, motivo: str):
    sessao.revogada_em = utcnow()
    sessao.motivo_revogacao = motivo
