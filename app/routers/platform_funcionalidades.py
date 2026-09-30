from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_platform_db
from app.models.platform_auth import PlatformTenant, PlatformFuncionalidade, PlatformTenantFuncionalidade
from app.schemas.platform_funcionalidades import (FuncionalidadeCreate, FuncionalidadeUpdate, FuncionalidadeResponse, HabilitacaoUpdate, HabilitacaoResponse)
from app.security.dependencies import require_platform_admin

router = APIRouter(prefix="/api/platform", tags=["Plataforma - Funcionalidades"], dependencies=[Depends(require_platform_admin)])

def commit(db):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Registro duplicado ou relacionamento invalido.") from exc

def tenant_existe(db, tenant_id):
    if not db.query(PlatformTenant.id).filter(PlatformTenant.id == tenant_id).first():
        raise HTTPException(status_code=404, detail="TENANT nao encontrado.")

def funcionalidade(db, id):
    obj = db.get(PlatformFuncionalidade, id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Funcionalidade nao encontrada.")
    return obj

@router.get("/funcionalidades", response_model=list[FuncionalidadeResponse])
def listar(db: Session = Depends(get_platform_db)):
    return db.query(PlatformFuncionalidade).order_by(PlatformFuncionalidade.ordem, PlatformFuncionalidade.nome).all()

@router.post("/funcionalidades", response_model=FuncionalidadeResponse, status_code=status.HTTP_201_CREATED)
def criar(dados: FuncionalidadeCreate, db: Session = Depends(get_platform_db)):
    obj = PlatformFuncionalidade(id=uuid4(), **dados.model_dump())
    db.add(obj); commit(db); db.refresh(obj)
    return obj

@router.get("/funcionalidades/{funcionalidade_id}", response_model=FuncionalidadeResponse)
def consultar(funcionalidade_id: UUID, db: Session = Depends(get_platform_db)):
    return funcionalidade(db, funcionalidade_id)

@router.patch("/funcionalidades/{funcionalidade_id}", response_model=FuncionalidadeResponse)
def atualizar(funcionalidade_id: UUID, dados: FuncionalidadeUpdate, db: Session = Depends(get_platform_db)):
    obj = funcionalidade(db, funcionalidade_id)
    changes = dados.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="Informe ao menos um campo.")
    for field, value in changes.items():
        if field in ("codigo", "nome", "ativo", "ordem") and value is None:
            raise HTTPException(status_code=422, detail=f"{field} nao aceita null.")
        setattr(obj, field, value)
    commit(db); db.refresh(obj)
    return obj

@router.get("/tenants/{tenant_id}/funcionalidades", response_model=list[HabilitacaoResponse])
def listar_habilitacoes(tenant_id: UUID, db: Session = Depends(get_platform_db)):
    tenant_existe(db, tenant_id)
    return db.query(PlatformTenantFuncionalidade).filter(PlatformTenantFuncionalidade.tenant_id == tenant_id).all()

@router.put("/tenants/{tenant_id}/funcionalidades/{funcionalidade_id}", response_model=HabilitacaoResponse)
def definir_habilitacao(tenant_id: UUID, funcionalidade_id: UUID, dados: HabilitacaoUpdate, db: Session = Depends(get_platform_db)):
    tenant_existe(db, tenant_id)
    funcionalidade(db, funcionalidade_id)
    obj = db.query(PlatformTenantFuncionalidade).filter(PlatformTenantFuncionalidade.tenant_id == tenant_id, PlatformTenantFuncionalidade.funcionalidade_id == funcionalidade_id).first()
    if obj is None:
        obj = PlatformTenantFuncionalidade(id=uuid4(), tenant_id=tenant_id, funcionalidade_id=funcionalidade_id, ativo=dados.ativo)
        db.add(obj)
    else:
        obj.ativo = dados.ativo
    commit(db); db.refresh(obj)
    return obj
