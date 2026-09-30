from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_platform_db
from app.models.platform_auth import PlatformTenant, PlatformTenantDatabase, PlatformTenantBranding
from app.schemas.platform_tenants import TenantCreate, TenantResponse, TenantUpdate
from app.schemas.platform_tenant_databases import TenantDatabaseCreate, TenantDatabaseUpdate, TenantDatabaseResponse
from app.schemas.platform_tenant_branding import TenantBrandingCreate, TenantBrandingUpdate, TenantBrandingResponse
from app.security.dependencies import require_platform_admin

router = APIRouter(
    prefix="/api/platform/tenants",
    tags=["Plataforma - TENANTs"],
    dependencies=[Depends(require_platform_admin)],
)


def _get_tenant(db: Session, tenant_id: UUID) -> PlatformTenant:
    tenant = db.query(PlatformTenant).filter(PlatformTenant.id == tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=404, detail="TENANT nao encontrado.")
    return tenant


def _commit_or_conflict(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Codigo ou slug ja utilizado por outro TENANT.",
        ) from exc


@router.get("/", response_model=list[TenantResponse])
def listar_tenants(db: Session = Depends(get_platform_db)):
    return db.query(PlatformTenant).order_by(PlatformTenant.nome).all()


@router.get("/{tenant_id}", response_model=TenantResponse)
def consultar_tenant(tenant_id: UUID, db: Session = Depends(get_platform_db)):
    return _get_tenant(db, tenant_id)


@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def criar_tenant(dados: TenantCreate, db: Session = Depends(get_platform_db)):
    tenant = PlatformTenant(id=uuid4(), **dados.model_dump())
    db.add(tenant)
    _commit_or_conflict(db)
    db.refresh(tenant)
    return tenant


@router.patch("/{tenant_id}", response_model=TenantResponse)
def atualizar_tenant(tenant_id: UUID, dados: TenantUpdate, db: Session = Depends(get_platform_db)):
    tenant = _get_tenant(db, tenant_id)
    alteracoes = dados.model_dump(exclude_unset=True)
    if not alteracoes:
        raise HTTPException(status_code=422, detail="Informe ao menos um campo para atualizar.")
    if any(valor is None for valor in alteracoes.values()):
        raise HTTPException(status_code=422, detail="Campos de TENANT nao aceitam null.")
    if tenant.tenant_sistema and alteracoes.get("ativo") is False:
        raise HTTPException(
            status_code=409,
            detail="O Tenant de sistema da Plataforma MDP nao pode ser inativado.",
        )
    for campo, valor in alteracoes.items():
        setattr(tenant, campo, valor)
    _commit_or_conflict(db)
    db.refresh(tenant)
    return tenant


def _get_database(db: Session, tenant_id: UUID) -> PlatformTenantDatabase:
    _get_tenant(db, tenant_id)
    registro = db.query(PlatformTenantDatabase).filter(PlatformTenantDatabase.tenant_id == tenant_id).first()
    if registro is None:
        raise HTTPException(status_code=404, detail="Banco do TENANT nao cadastrado.")
    return registro


@router.get("/{tenant_id}/database", response_model=TenantDatabaseResponse)
def consultar_banco_tenant(tenant_id: UUID, db: Session = Depends(get_platform_db)):
    return _get_database(db, tenant_id)


@router.post("/{tenant_id}/database", response_model=TenantDatabaseResponse, status_code=status.HTTP_201_CREATED)
def cadastrar_banco_tenant(tenant_id: UUID, dados: TenantDatabaseCreate, db: Session = Depends(get_platform_db)):
    _get_tenant(db, tenant_id)
    existente = db.query(PlatformTenantDatabase.id).filter(PlatformTenantDatabase.tenant_id == tenant_id).first()
    if existente:
        raise HTTPException(status_code=409, detail="TENANT ja possui banco cadastrado.")
    registro = PlatformTenantDatabase(id=uuid4(), tenant_id=tenant_id, **dados.model_dump())
    db.add(registro)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="TENANT ou nome do banco ja cadastrado.") from exc
    db.refresh(registro)
    return registro


@router.patch("/{tenant_id}/database", response_model=TenantDatabaseResponse)
def atualizar_banco_tenant(tenant_id: UUID, dados: TenantDatabaseUpdate, db: Session = Depends(get_platform_db)):
    registro = _get_database(db, tenant_id)
    alteracoes = dados.model_dump(exclude_unset=True)
    if not alteracoes:
        raise HTTPException(status_code=422, detail="Informe ao menos um campo.")
    for campo, valor in alteracoes.items():
        if valor is None and campo not in {"secret_ref", "versao_schema"}:
            raise HTTPException(status_code=422, detail=f"{campo} nao aceita null.")
        setattr(registro, campo, valor)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Nome do banco ja utilizado.") from exc
    db.refresh(registro)
    return registro


def _get_branding(db: Session, tenant_id: UUID) -> PlatformTenantBranding:
    _get_tenant(db, tenant_id)
    registro = db.query(PlatformTenantBranding).filter(PlatformTenantBranding.tenant_id == tenant_id).first()
    if registro is None:
        raise HTTPException(status_code=404, detail="Branding do TENANT nao cadastrado.")
    return registro

def _normalize_branding(data: dict) -> dict:
    if "admin_host" in data and data["admin_host"]:
        data["admin_host"] = data["admin_host"].strip().lower().rstrip(".")
    for campo in ("nome_exibicao", "logo_url", "favicon_url", "cor_primaria"):
        if campo in data and isinstance(data[campo], str):
            data[campo] = data[campo].strip() or None
    return data

@router.get("/{tenant_id}/branding", response_model=TenantBrandingResponse)
def consultar_branding_tenant(tenant_id: UUID, db: Session = Depends(get_platform_db)):
    return _get_branding(db, tenant_id)

@router.post("/{tenant_id}/branding", response_model=TenantBrandingResponse, status_code=status.HTTP_201_CREATED)
def cadastrar_branding_tenant(tenant_id: UUID, dados: TenantBrandingCreate, db: Session = Depends(get_platform_db)):
    _get_tenant(db, tenant_id)
    if db.query(PlatformTenantBranding.id).filter(PlatformTenantBranding.tenant_id == tenant_id).first():
        raise HTTPException(status_code=409, detail="TENANT ja possui configuracao de dominio/branding.")
    registro = PlatformTenantBranding(id=uuid4(), tenant_id=tenant_id, **_normalize_branding(dados.model_dump()))
    db.add(registro)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Dominio/host ja utilizado por outro TENANT.") from exc
    db.refresh(registro)
    return registro

@router.patch("/{tenant_id}/branding", response_model=TenantBrandingResponse)
def atualizar_branding_tenant(tenant_id: UUID, dados: TenantBrandingUpdate, db: Session = Depends(get_platform_db)):
    registro = _get_branding(db, tenant_id)
    alteracoes = _normalize_branding(dados.model_dump(exclude_unset=True))
    if not alteracoes:
        raise HTTPException(status_code=422, detail="Informe ao menos um campo.")
    for campo, valor in alteracoes.items():
        if campo == "ativo" and valor is None:
            raise HTTPException(status_code=422, detail="ativo nao aceita null.")
        setattr(registro, campo, valor)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Dominio/host ja utilizado por outro TENANT.") from exc
    db.refresh(registro)
    return registro
