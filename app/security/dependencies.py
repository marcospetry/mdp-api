from datetime import datetime, timezone
from uuid import UUID
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_platform_db, tenant_session
from app.models.auth import PerfilPermissao, UsuarioEmpresa, UsuarioTenantLocal
from app.models.platform_auth import PlatformSessaoUsuario, PlatformTenant, PlatformUsuario, PlatformUsuarioTenant
from app.security.jwt import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    platform_db: Session = Depends(get_platform_db),
):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação necessária.")
    try:
        payload = decode_token(credentials.credentials, "access")
        usuario_id = UUID(payload["sub"])
        sessao_id = UUID(payload["sid"])
        tenant_id = UUID(payload["tenant_id"]) if payload.get("tenant_id") else None
        empresa_id = UUID(payload["empresa_id"]) if payload.get("empresa_id") else None
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado.")

    usuario = platform_db.query(PlatformUsuario).filter(PlatformUsuario.id == usuario_id, PlatformUsuario.ativo.is_(True)).first()
    sessao = platform_db.query(PlatformSessaoUsuario).filter(PlatformSessaoUsuario.id == sessao_id, PlatformSessaoUsuario.usuario_id == usuario_id).first()
    if not usuario or not sessao or sessao.revogada_em is not None or sessao.expira_em <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida.")
    if usuario.acesso_expira_em and usuario.acesso_expira_em <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Acesso expirado.")
    if sessao.contexto_tipo is not None:
        if sessao.tenant_id != tenant_id or sessao.empresa_id != empresa_id:
            raise HTTPException(status_code=401, detail="Contexto da sessão inválido.")
    if tenant_id is None:
        if payload.get("contexto_tipo") != "PLATAFORMA" or sessao.contexto_tipo != "PLATAFORMA" or not usuario.is_superadmin:
            raise HTTPException(status_code=403, detail="Acesso à Plataforma não autorizado.")
        return {"usuario": usuario, "usuario_local": None, "sessao": sessao,
                "empresa_id": None, "vinculo": None, "tenant_id": None,
                "vinculo_tenant": None, "contexto_tipo": "PLATAFORMA"}
    if payload.get("contexto_tipo") not in (None, "TENANT"):
        raise HTTPException(status_code=401, detail="Contexto inválido.")
    vinculo_tenant = platform_db.query(PlatformUsuarioTenant).filter(
        PlatformUsuarioTenant.usuario_id == usuario_id,
        PlatformUsuarioTenant.tenant_id == tenant_id,
        PlatformUsuarioTenant.ativo.is_(True),
    ).first()
    tenant_ativo = platform_db.query(PlatformTenant.id).filter(PlatformTenant.id == tenant_id, PlatformTenant.ativo.is_(True)).first()
    if (not vinculo_tenant and not usuario.is_superadmin) or not tenant_ativo:
        raise HTTPException(status_code=403, detail="Tenant não autorizado.")
    with tenant_session(platform_db, tenant_id) as tenant_db:
        usuario_local = tenant_db.query(UsuarioTenantLocal).filter(
            UsuarioTenantLocal.platform_usuario_id == usuario_id,
            UsuarioTenantLocal.ativo.is_(True),
        ).first()
        if not usuario_local:
            raise HTTPException(status_code=403, detail="Usuário não provisionado no Tenant.")

        vinculo = None
        if empresa_id:
            vinculo = tenant_db.query(UsuarioEmpresa).filter(
                UsuarioEmpresa.usuario_id == usuario_local.id,
                UsuarioEmpresa.empresa_id == empresa_id,
                UsuarioEmpresa.ativo.is_(True),
            ).first()
            if not vinculo:
                raise HTTPException(status_code=403, detail="Usuário sem acesso à empresa no Tenant.")
            _ = vinculo.perfil  # carrega antes de fechar a sessão

        return {
            "usuario": usuario,
            "usuario_local": usuario_local,
            "sessao": sessao,
            "empresa_id": empresa_id,
            "vinculo": vinculo,
            "tenant_id": tenant_id,
            "vinculo_tenant": vinculo_tenant,
            "contexto_tipo": "TENANT",
        }


def require_tenant_context(context=Depends(get_current_context)):
    if (context.get("contexto_tipo") != "TENANT" or not context.get("tenant_id") or (not context.get("vinculo_tenant") and not context["usuario"].is_superadmin)):
        raise HTTPException(status_code=403, detail="Contexto TENANT necessario.")
    return context


def require_backoffice_context(context=Depends(require_tenant_context), platform_db: Session = Depends(get_platform_db)):
    """Backoffice (cadastros, diagnostico): bloqueia perfis que SO possuem permissoes do Omni (OMNI_*).

    Perfis com acesso_total (ADMIN) passam direto, sem consulta extra. Os demais so sao barrados
    se tiverem permissoes e todas forem OMNI_* (ex.: OMNI_OPERADOR, usado pelo revisor da Meta)."""
    vinculo = context.get("vinculo")
    if not vinculo or vinculo.perfil.acesso_total:
        return context
    with tenant_session(platform_db, context["tenant_id"]) as tenant_db:
        codigos = [
            r.permissao.codigo
            for r in tenant_db.query(PerfilPermissao).filter(PerfilPermissao.perfil_id == vinculo.perfil_id).all()
            if r.permissao.ativo
        ]
    if codigos and all(c.startswith("OMNI_") for c in codigos):
        raise HTTPException(status_code=403, detail="Perfil sem acesso ao backoffice.")
    return context


def get_current_user(context=Depends(get_current_context)):
    return context["usuario"]


def get_authorized_tenant_db(context=Depends(require_tenant_context), platform_db: Session = Depends(get_platform_db)):
    with tenant_session(platform_db, context["tenant_id"]) as db:
        yield db


def require_permission(codigo: str):
    def dependency(context=Depends(get_current_context), db: Session = Depends(get_authorized_tenant_db)):
        vinculo = context["vinculo"]
        if not vinculo:
            raise HTTPException(status_code=403, detail="Empresa ativa não definida.")
        if vinculo.perfil.acesso_total:
            return context
        existe = db.query(PerfilPermissao).join(PerfilPermissao.permissao).filter(
            PerfilPermissao.perfil_id == vinculo.perfil_id,
            PerfilPermissao.permissao.has(codigo=codigo, ativo=True),
        ).first()
        if not existe:
            raise HTTPException(status_code=403, detail="Permissão insuficiente.")
        return context
    return dependency


def require_empresa_access(context: dict, empresa_id: UUID):
    if context.get("empresa_id") != empresa_id or not context.get("vinculo"):
        # SUPERADMIN da plataforma pode administrar o conjunto de empresas do Tenant
        # somente quando também está provisionado no Tenant (garantido pelo contexto).
        if not context["usuario"].is_superadmin:
            raise HTTPException(status_code=403, detail="Acesso negado à empresa informada.")


def require_tenant_access(context: dict, tenant_id: UUID):
    if context.get("tenant_id") != tenant_id or (not context.get("vinculo_tenant") and not context["usuario"].is_superadmin):
        raise HTTPException(status_code=403, detail="Acesso negado ao Tenant informado.")
    return context["vinculo_tenant"]


def require_unidade_access(db: Session, context: dict, unidade_id: UUID):
    from app.models.organizacao import UnidadeEmpresa, UsuarioUnidade
    unidade = db.query(UnidadeEmpresa).filter(UnidadeEmpresa.id == unidade_id).first()
    if not unidade:
        raise HTTPException(status_code=404, detail="Unidade não encontrada.")
    require_empresa_access(context, unidade.empresa_id)
    if context["usuario"].is_superadmin:
        return unidade
    vinculo = context["vinculo"]
    if vinculo.acesso_todas_unidades:
        return unidade
    permitido = db.query(UsuarioUnidade.id).filter(UsuarioUnidade.usuario_empresa_id == vinculo.id, UsuarioUnidade.unidade_id == unidade.id).first()
    if not permitido:
        raise HTTPException(status_code=403, detail="Usuário sem acesso a esta unidade.")
    return unidade


def require_area_access(db: Session, context: dict, area_id: UUID):
    from app.models.organizacao import Area, UsuarioArea
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Área não encontrada.")
    require_empresa_access(context, area.empresa_id)
    if context["usuario"].is_superadmin:
        return area
    vinculo = context["vinculo"]
    if vinculo.acesso_todas_areas:
        return area
    permitido = db.query(UsuarioArea.id).filter(UsuarioArea.usuario_empresa_id == vinculo.id, UsuarioArea.area_id == area.id).first()
    if not permitido:
        raise HTTPException(status_code=403, detail="Usuário sem acesso a esta área.")
    return area


def require_platform_admin(context=Depends(get_current_context)):
    if context.get("contexto_tipo") != "PLATAFORMA" or not context["usuario"].is_superadmin:
        raise HTTPException(status_code=403, detail="Administração da Plataforma não autorizada.")
    return context
