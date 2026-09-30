from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_platform_db
from app.models.platform_auth import PlatformTenant, PlatformUsuario, PlatformUsuarioTenant
from app.schemas.platform_usuarios import (
    PlatformUsuarioDetalhe,
    PlatformUsuarioResumo,
    PlatformUsuarioTenantResumo,
    PlatformUsuarioUpdate,
    TenantUsuarioResponse,
    TenantUsuarioVinculoCreate,
    TenantUsuarioVinculoUpdate,
)
from app.security.dependencies import require_platform_admin

router = APIRouter(
    prefix="/api/platform",
    tags=["Plataforma - Usuarios e acessos"],
    dependencies=[Depends(require_platform_admin)],
)


def _tenant(db: Session, tenant_id: UUID) -> PlatformTenant:
    tenant = db.query(PlatformTenant).filter(PlatformTenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="TENANT nao encontrado.")
    return tenant


def _usuario(db: Session, usuario_id: UUID) -> PlatformUsuario:
    usuario = db.query(PlatformUsuario).filter(PlatformUsuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario da Plataforma nao encontrado.")
    return usuario


def _vinculo_response(vinculo: PlatformUsuarioTenant, usuario: PlatformUsuario) -> TenantUsuarioResponse:
    return TenantUsuarioResponse(
        vinculo_id=vinculo.id,
        usuario_id=usuario.id,
        nome=usuario.nome,
        email=usuario.email,
        is_superadmin=usuario.is_superadmin,
        usuario_ativo=usuario.ativo,
        vinculo_ativo=vinculo.ativo,
    )


def _usuario_detalhe(db: Session, usuario: PlatformUsuario) -> PlatformUsuarioDetalhe:
    tenants = db.query(PlatformTenant).order_by(PlatformTenant.nome).all()
    vinculos = db.query(PlatformUsuarioTenant).filter(PlatformUsuarioTenant.usuario_id == usuario.id).all()
    por_tenant = {v.tenant_id: v for v in vinculos}
    return PlatformUsuarioDetalhe(
        id=usuario.id, nome=usuario.nome, email=usuario.email,
        is_superadmin=usuario.is_superadmin, ativo=usuario.ativo,
        tenants=[PlatformUsuarioTenantResumo(
            vinculo_id=por_tenant[t.id].id if t.id in por_tenant else None,
            tenant_id=t.id, tenant_codigo=t.codigo, tenant_nome=t.nome,
            tenant_ativo=t.ativo,
            vinculo_ativo=bool(t.id in por_tenant and por_tenant[t.id].ativo),
        ) for t in tenants],
    )


@router.get("/usuarios", response_model=list[PlatformUsuarioResumo])
def listar_usuarios(db: Session = Depends(get_platform_db)):
    return db.query(PlatformUsuario).order_by(PlatformUsuario.nome, PlatformUsuario.email).all()


@router.get("/usuarios/{usuario_id}", response_model=PlatformUsuarioDetalhe)
def obter_usuario(usuario_id: UUID, db: Session = Depends(get_platform_db)):
    return _usuario_detalhe(db, _usuario(db, usuario_id))


@router.patch("/usuarios/{usuario_id}", response_model=PlatformUsuarioDetalhe)
def atualizar_usuario(usuario_id: UUID, dados: PlatformUsuarioUpdate, db: Session = Depends(get_platform_db)):
    usuario = _usuario(db, usuario_id)
    alteracoes = dados.model_dump(exclude_unset=True)
    if "email" in alteracoes:
        email = str(alteracoes["email"]).strip().lower()
        conflito = db.query(PlatformUsuario).filter(PlatformUsuario.email == email, PlatformUsuario.id != usuario.id).first()
        if conflito:
            raise HTTPException(status_code=409, detail="Ja existe usuario central com este e-mail.")
        alteracoes["email"] = email
    if alteracoes.get("ativo") is False and usuario.is_superadmin:
        outros = db.query(PlatformUsuario).filter(
            PlatformUsuario.is_superadmin.is_(True), PlatformUsuario.ativo.is_(True), PlatformUsuario.id != usuario.id
        ).count()
        if outros == 0:
            raise HTTPException(status_code=409, detail="Nao e permitido inativar o ultimo SUPERADMIN ativo da Plataforma.")
    for campo, valor in alteracoes.items():
        setattr(usuario, campo, valor)
    db.commit(); db.refresh(usuario)
    return _usuario_detalhe(db, usuario)


@router.get("/tenants/{tenant_id}/usuarios", response_model=list[TenantUsuarioResponse])
def listar_usuarios_tenant(tenant_id: UUID, db: Session = Depends(get_platform_db)):
    _tenant(db, tenant_id)
    rows = (
        db.query(PlatformUsuarioTenant, PlatformUsuario)
        .join(PlatformUsuario, PlatformUsuario.id == PlatformUsuarioTenant.usuario_id)
        .filter(PlatformUsuarioTenant.tenant_id == tenant_id)
        .order_by(PlatformUsuario.nome, PlatformUsuario.email)
        .all()
    )
    return [_vinculo_response(v, u) for v, u in rows]


@router.post("/tenants/{tenant_id}/usuarios", response_model=TenantUsuarioResponse, status_code=status.HTTP_201_CREATED)
def vincular_usuario_tenant(tenant_id: UUID, dados: TenantUsuarioVinculoCreate, db: Session = Depends(get_platform_db)):
    _tenant(db, tenant_id)
    usuario = _usuario(db, dados.usuario_id)
    existente = db.query(PlatformUsuarioTenant).filter(
        PlatformUsuarioTenant.tenant_id == tenant_id,
        PlatformUsuarioTenant.usuario_id == dados.usuario_id,
    ).first()
    if existente:
        if existente.ativo:
            raise HTTPException(status_code=409, detail="Usuario ja esta vinculado a este Tenant.")
        existente.ativo = True
        db.commit(); db.refresh(existente)
        return _vinculo_response(existente, usuario)
    vinculo = PlatformUsuarioTenant(id=uuid4(), tenant_id=tenant_id, usuario_id=dados.usuario_id, ativo=True)
    db.add(vinculo); db.commit(); db.refresh(vinculo)
    return _vinculo_response(vinculo, usuario)


@router.patch("/tenants/{tenant_id}/usuarios/{vinculo_id}", response_model=TenantUsuarioResponse)
def atualizar_vinculo_usuario(tenant_id: UUID, vinculo_id: UUID, dados: TenantUsuarioVinculoUpdate, db: Session = Depends(get_platform_db)):
    _tenant(db, tenant_id)
    vinculo = db.query(PlatformUsuarioTenant).filter(
        PlatformUsuarioTenant.id == vinculo_id,
        PlatformUsuarioTenant.tenant_id == tenant_id,
    ).first()
    if not vinculo:
        raise HTTPException(status_code=404, detail="Vinculo usuario x Tenant nao encontrado.")
    usuario = _usuario(db, vinculo.usuario_id)
    vinculo.ativo = dados.ativo
    db.commit(); db.refresh(vinculo)
    return _vinculo_response(vinculo, usuario)
