from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_platform_db
from app.models.platform_auth import PlatformTenant, PlatformTenantEndpoint, PlatformTipoEndpoint
from app.schemas.platform_tenant_endpoints import EndpointCreate, EndpointUpdate, EndpointResponse
from app.security.dependencies import require_platform_admin

router = APIRouter(prefix="/api/platform/tenants/{tenant_id}/endpoints", tags=["Plataforma - Endpoints"], dependencies=[Depends(require_platform_admin)])

def _tenant(db, tenant_id):
    if db.query(PlatformTenant.id).filter(PlatformTenant.id == tenant_id).first() is None: raise HTTPException(404,"TENANT nao encontrado.")
def _endpoint(db,tenant_id,endpoint_id):
    x=db.query(PlatformTenantEndpoint).filter(PlatformTenantEndpoint.id==endpoint_id,PlatformTenantEndpoint.tenant_id==tenant_id).first()
    if x is None: raise HTTPException(404,"Endpoint nao encontrado neste TENANT.")
    return x
def _tipo(db,tipo_id):
    x=db.query(PlatformTipoEndpoint).filter(PlatformTipoEndpoint.id==tipo_id).first()
    if x is None: raise HTTPException(422,"Tipo de canal inexistente.")
    if not x.ativo: raise HTTPException(422,"Tipo de canal inativo na Plataforma.")
    return x
def _commit(db):
    try: db.commit()
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(409,"Codigo de endpoint ja utilizado neste TENANT.") from exc
def _resp(item,tipo):
    return EndpointResponse(id=item.id,tenant_id=item.tenant_id,tipo_endpoint_id=item.tipo_endpoint_id,tipo=tipo.codigo,tipo_nome=tipo.nome,codigo=item.codigo,nome=item.nome,identificador_publico=item.identificador_publico,identificador_externo=item.identificador_externo,url=item.url,ativo=item.ativo)

def _rows(db,tenant_id):
    return db.query(PlatformTenantEndpoint,PlatformTipoEndpoint).join(PlatformTipoEndpoint,PlatformTipoEndpoint.id==PlatformTenantEndpoint.tipo_endpoint_id).filter(PlatformTenantEndpoint.tenant_id==tenant_id).order_by(PlatformTenantEndpoint.nome).all()

@router.get("/",response_model=list[EndpointResponse])
def listar(tenant_id:UUID,db:Session=Depends(get_platform_db)):
    _tenant(db,tenant_id); return [_resp(e,t) for e,t in _rows(db,tenant_id)]

@router.get("/{endpoint_id}",response_model=EndpointResponse)
def consultar(tenant_id:UUID,endpoint_id:UUID,db:Session=Depends(get_platform_db)):
    _tenant(db,tenant_id); e=_endpoint(db,tenant_id,endpoint_id); t=db.query(PlatformTipoEndpoint).filter(PlatformTipoEndpoint.id==e.tipo_endpoint_id).first(); return _resp(e,t)

@router.post("/",response_model=EndpointResponse,status_code=status.HTTP_201_CREATED)
def criar(tenant_id:UUID,dados:EndpointCreate,db:Session=Depends(get_platform_db)):
    _tenant(db,tenant_id); t=_tipo(db,dados.tipo_endpoint_id); e=PlatformTenantEndpoint(id=uuid4(),tenant_id=tenant_id,**dados.model_dump()); db.add(e); _commit(db); db.refresh(e); return _resp(e,t)

@router.patch("/{endpoint_id}",response_model=EndpointResponse)
def atualizar(tenant_id:UUID,endpoint_id:UUID,dados:EndpointUpdate,db:Session=Depends(get_platform_db)):
    _tenant(db,tenant_id); e=_endpoint(db,tenant_id,endpoint_id); alt=dados.model_dump(exclude_unset=True)
    if not alt: raise HTTPException(422,"Informe ao menos um campo.")
    if "tipo_endpoint_id" in alt:
        if alt["tipo_endpoint_id"] is None: raise HTTPException(422,"tipo_endpoint_id nao aceita null.")
        _tipo(db,alt["tipo_endpoint_id"])
    for k,v in alt.items():
        if v is None and k in {"codigo","nome","ativo"}: raise HTTPException(422,f"{k} nao aceita null.")
        setattr(e,k,v)
    _commit(db); db.refresh(e); t=db.query(PlatformTipoEndpoint).filter(PlatformTipoEndpoint.id==e.tipo_endpoint_id).first(); return _resp(e,t)
