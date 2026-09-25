from uuid import UUID
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_platform_db, get_tenant_db
from app.models.auth import PerfilPermissao, UsuarioEmpresa, UsuarioTenantLocal
from app.models.platform_auth import PlatformSessaoUsuario, PlatformUsuario, PlatformUsuarioTenant
from app.security.jwt import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    platform_db: Session = Depends(get_platform_db),
    tenant_db: Session = Depends(get_tenant_db),
):
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação necessária.")
    try:
        payload = decode_token(credentials.credentials, "access")
        usuario_id = UUID(payload["sub"])
        sessao_id = UUID(payload["sid"])
        tenant_id = UUID(payload["tenant_id"])
        empresa_id = UUID(payload["empresa_id"]) if payload.get("empresa_id") else None
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado.")

    usuario = platform_db.query(PlatformUsuario).filter(PlatformUsuario.id == usuario_id, PlatformUsuario.ativo.is_(True)).first()
    sessao = platform_db.query(PlatformSessaoUsuario).filter(PlatformSessaoUsuario.id == sessao_id, PlatformSessaoUsuario.usuario_id == usuario_id).first()
    vinculo_tenant = platform_db.query(PlatformUsuarioTenant).filter(
        PlatformUsuarioTenant.usuario_id == usuario_id,
        PlatformUsuarioTenant.tenant_id == tenant_id,
        PlatformUsuarioTenant.ativo.is_(True),
    ).first()
    if not usuario or not sessao or sessao.revogada_em is not None or not vinculo_tenant:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão ou Tenant inválido.")

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

    return {
        "usuario": usuario,
        "usuario_local": usuario_local,
        "sessao": sessao,
        "empresa_id": empresa_id,
        "vinculo": vinculo,
        "tenant_id": tenant_id,
        "vinculo_tenant": vinculo_tenant,
    }


def get_current_user(context=Depends(get_current_context)):
    return context["usuario"]


def require_permission(codigo: str):
    def dependency(context=Depends(get_current_context), db: Session = Depends(get_tenant_db)):
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
    if context.get("tenant_id") != tenant_id or not context.get("vinculo_tenant"):
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
