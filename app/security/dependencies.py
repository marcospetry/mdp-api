from uuid import UUID
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import PerfilPermissao, SessaoUsuario, Usuario, UsuarioEmpresa
from app.security.jwt import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
):
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
