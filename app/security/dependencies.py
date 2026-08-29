from uuid import UUID
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.auth import PerfilPermissao, SessaoUsuario, Usuario, UsuarioEmpresa
from app.models.empresa import Empresa
from app.security.jwt import decode_token

bearer = HTTPBearer(auto_error=False)


_LOCAL_DEV_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def _dev_context(request: Request, db: Session):
    """Retorna contexto autenticado apenas para desenvolvimento local explícito.

    O bypass nunca fica ativo apenas por DEV_AUTH_BYPASS=true: também exige
    APP_ENV=development e origem local. Produção mantém o fluxo JWT/MFA normal.
    """
    if not settings.dev_auth_enabled:
        return None

    client_host = request.client.host if request.client else None
    if client_host not in _LOCAL_DEV_HOSTS:
        return None

    empresa = db.query(Empresa).filter(
        Empresa.slug == settings.dev_auth_empresa_slug,
        Empresa.ativo.is_(True),
    ).first()
    if not empresa:
        raise HTTPException(
            status_code=500,
            detail=f"DEV_AUTH: empresa '{settings.dev_auth_empresa_slug}' não encontrada ou inativa.",
        )

    q = db.query(Usuario).join(UsuarioEmpresa, UsuarioEmpresa.usuario_id == Usuario.id).filter(
        UsuarioEmpresa.empresa_id == empresa.id,
        UsuarioEmpresa.ativo.is_(True),
        Usuario.ativo.is_(True),
    )
    if settings.dev_auth_usuario_email:
        q = q.filter(Usuario.email == settings.dev_auth_usuario_email)
    else:
        q = q.filter(Usuario.is_superadmin.is_(True))

    usuario = q.order_by(Usuario.created_at).first()
    if not usuario:
        criterio = settings.dev_auth_usuario_email or "superadmin ativo"
        raise HTTPException(
            status_code=500,
            detail=f"DEV_AUTH: usuário de desenvolvimento não encontrado ({criterio}).",
        )

    vinculo = db.query(UsuarioEmpresa).filter(
        UsuarioEmpresa.usuario_id == usuario.id,
        UsuarioEmpresa.empresa_id == empresa.id,
        UsuarioEmpresa.ativo.is_(True),
    ).first()

    return {
        "usuario": usuario,
        "sessao": None,
        "empresa_id": empresa.id,
        "vinculo": vinculo,
        "dev_auth_bypass": True,
    }


def get_current_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
    dev_context = _dev_context(request, db)
    if dev_context is not None:
        return dev_context

    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação necessária.")
    try:
        payload = decode_token(credentials.credentials, "access")
        usuario_id = UUID(payload["sub"])
        sessao_id = UUID(payload["sid"])
        empresa_id = UUID(payload["empresa_id"]) if payload.get("empresa_id") else None
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado.")

    usuario = db.query(Usuario).filter(Usuario.id == usuario_id, Usuario.ativo.is_(True)).first()
    sessao = db.query(SessaoUsuario).filter(SessaoUsuario.id == sessao_id, SessaoUsuario.usuario_id == usuario_id).first()
    if not usuario or not sessao or sessao.revogada_em is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida.")

    vinculo = None
    if empresa_id:
        vinculo = db.query(UsuarioEmpresa).filter(
            UsuarioEmpresa.usuario_id == usuario_id,
            UsuarioEmpresa.empresa_id == empresa_id,
            UsuarioEmpresa.ativo.is_(True),
        ).first()
        if not vinculo and not usuario.is_superadmin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário sem acesso à empresa.")

    return {"usuario": usuario, "sessao": sessao, "empresa_id": empresa_id, "vinculo": vinculo}


def get_current_user(context=Depends(get_current_context)):
    return context["usuario"]


def require_permission(codigo: str):
    def dependency(context=Depends(get_current_context), db: Session = Depends(get_db)):
        usuario = context["usuario"]
        if usuario.is_superadmin:
            return context
        vinculo = context["vinculo"]
        if not vinculo:
            raise HTTPException(status_code=403, detail="Empresa ativa não definida.")
        existe = db.query(PerfilPermissao).join(PerfilPermissao.permissao).filter(
            PerfilPermissao.perfil_id == vinculo.perfil_id,
            PerfilPermissao.permissao.has(codigo=codigo, ativo=True),
        ).first()
        if not existe:
            raise HTTPException(status_code=403, detail="Permissão insuficiente.")
        return context
    return dependency


def require_empresa_access(context: dict, empresa_id: UUID):
    """Garante que um usuário não-superadmin opere apenas na empresa ativa do token."""
    usuario = context["usuario"]
    if usuario.is_superadmin:
        return
    if context.get("empresa_id") != empresa_id or not context.get("vinculo"):
        raise HTTPException(status_code=403, detail="Acesso negado à empresa informada.")


def require_unidade_access(db: Session, context: dict, unidade_id: UUID):
    from app.models.organizacao import UnidadeEmpresa, UsuarioUnidade

    unidade = db.query(UnidadeEmpresa).filter(UnidadeEmpresa.id == unidade_id).first()
    if not unidade:
        raise HTTPException(status_code=404, detail="Unidade não encontrada.")
    require_empresa_access(context, unidade.empresa_id)
    usuario = context["usuario"]
    if usuario.is_superadmin:
        return unidade
    vinculo = context["vinculo"]
    if vinculo.acesso_todas_unidades:
        return unidade
    permitido = db.query(UsuarioUnidade.id).filter(
        UsuarioUnidade.usuario_empresa_id == vinculo.id,
        UsuarioUnidade.unidade_id == unidade.id,
    ).first()
    if not permitido:
        raise HTTPException(status_code=403, detail="Usuário sem acesso a esta unidade.")
    return unidade


def require_area_access(db: Session, context: dict, area_id: UUID):
    from app.models.organizacao import Area, UsuarioArea

    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Área não encontrada.")
    require_empresa_access(context, area.empresa_id)
    usuario = context["usuario"]
    if usuario.is_superadmin:
        return area
    vinculo = context["vinculo"]
    if vinculo.acesso_todas_areas:
        return area
    permitido = db.query(UsuarioArea.id).filter(
        UsuarioArea.usuario_empresa_id == vinculo.id,
        UsuarioArea.area_id == area.id,
    ).first()
    if not permitido:
        raise HTTPException(status_code=403, detail="Usuário sem acesso a esta área.")
    return area
