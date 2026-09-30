from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_platform_db
from app.models.platform_auth import PlatformTipoEndpoint
from app.schemas.platform_tipos_endpoint import TipoEndpointCreate, TipoEndpointUpdate, TipoEndpointResponse
from app.security.dependencies import require_platform_admin

router = APIRouter(prefix="/api/platform/tipos-endpoint", tags=["Plataforma - Tipos de Canal"], dependencies=[Depends(require_platform_admin)])

def _item(db: Session, item_id: UUID):
    item = db.query(PlatformTipoEndpoint).filter(PlatformTipoEndpoint.id == item_id).first()
    if item is None: raise HTTPException(status_code=404, detail="Tipo de canal nao encontrado.")
    return item

def _commit(db):
    try: db.commit()
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="Codigo de tipo de canal ja utilizado.") from exc

@router.get("", response_model=list[TipoEndpointResponse])
@router.get("/", response_model=list[TipoEndpointResponse], include_in_schema=False)
def listar(db: Session = Depends(get_platform_db)):
    return db.query(PlatformTipoEndpoint).order_by(PlatformTipoEndpoint.ordem, PlatformTipoEndpoint.nome).all()

@router.post("", response_model=TipoEndpointResponse, status_code=status.HTTP_201_CREATED)
def criar(dados: TipoEndpointCreate, db: Session = Depends(get_platform_db)):
    item = PlatformTipoEndpoint(id=uuid4(), **dados.model_dump())
    item.codigo = item.codigo.strip().upper()
    db.add(item); _commit(db); db.refresh(item); return item

@router.patch("/{item_id}", response_model=TipoEndpointResponse)
def atualizar(item_id: UUID, dados: TipoEndpointUpdate, db: Session = Depends(get_platform_db)):
    item = _item(db,item_id); alt=dados.model_dump(exclude_unset=True)
    if not alt: raise HTTPException(status_code=422, detail="Informe ao menos um campo.")
    for k,v in alt.items():
        if v is None and k in {"nome","ordem","ativo"}: raise HTTPException(status_code=422, detail=f"{k} nao aceita null.")
        setattr(item,k,v)
    _commit(db); db.refresh(item); return item
