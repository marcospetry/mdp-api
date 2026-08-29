from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.manutencao import OrigemContato, TipoInteracao
from app.schemas.manutencao import CatalogoCreate, CatalogoResponse, CatalogoStatus, CatalogoUpdate
from app.security.dependencies import get_current_context, require_empresa_access

router = APIRouter(prefix="/api/admin", tags=["Admin - Manutenção"], dependencies=[Depends(get_current_context)])

def _listar(db, model, empresa_id, context):
    require_empresa_access(context, empresa_id)
    return db.query(model).filter(or_(model.empresa_id.is_(None), model.empresa_id == empresa_id)).order_by(model.ordem, model.nome).all()

def _criar(db, model, empresa_id, dados, context):
    require_empresa_access(context, empresa_id)
    ordem = dados.ordem or ((db.query(func.max(model.ordem)).filter(model.empresa_id == empresa_id).scalar() or 0) + 1)
    obj = model(empresa_id=empresa_id, codigo=dados.codigo.strip().upper(), nome=dados.nome.strip(), descricao=dados.descricao, ordem=ordem, padrao_sistema=False)
    db.add(obj)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409, "Código já cadastrado neste escopo.")
    db.refresh(obj); return obj

def _proprio(db, model, obj_id, context):
    obj=db.query(model).filter(model.id==obj_id).first()
    if not obj: raise HTTPException(404, "Registro não encontrado.")
    if obj.empresa_id is None:
        if not (context["usuario"].is_superadmin or context.get("dev_auth_bypass")):
            raise HTTPException(403, "Padrão global MDP protegido.")
    else: require_empresa_access(context, obj.empresa_id)
    return obj

def _editar(db, model, obj_id, dados, context):
    obj=_proprio(db,model,obj_id,context)
    vals=dados.model_dump(exclude_unset=True)
    if "codigo" in vals: vals["codigo"]=vals["codigo"].strip().upper()
    if "nome" in vals: vals["nome"]=vals["nome"].strip()
    for k,v in vals.items(): setattr(obj,k,v)
    try: db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(409,"Código já cadastrado neste escopo.")
    db.refresh(obj); return obj

def _status(db, model, obj_id, dados, context):
    obj=_proprio(db,model,obj_id,context); obj.ativo=dados.ativo; db.commit(); db.refresh(obj); return obj

@router.get("/empresas/{empresa_id}/origens-contato", response_model=list[CatalogoResponse])
def listar_origens(empresa_id:UUID,db:Session=Depends(get_db),context=Depends(get_current_context)): return _listar(db,OrigemContato,empresa_id,context)
@router.post("/empresas/{empresa_id}/origens-contato",response_model=CatalogoResponse,status_code=status.HTTP_201_CREATED)
def criar_origem(empresa_id:UUID,dados:CatalogoCreate,db:Session=Depends(get_db),context=Depends(get_current_context)): return _criar(db,OrigemContato,empresa_id,dados,context)
@router.put("/origens-contato/{obj_id}",response_model=CatalogoResponse)
def editar_origem(obj_id:UUID,dados:CatalogoUpdate,db:Session=Depends(get_db),context=Depends(get_current_context)): return _editar(db,OrigemContato,obj_id,dados,context)
@router.patch("/origens-contato/{obj_id}/status",response_model=CatalogoResponse)
def status_origem(obj_id:UUID,dados:CatalogoStatus,db:Session=Depends(get_db),context=Depends(get_current_context)): return _status(db,OrigemContato,obj_id,dados,context)

@router.get("/empresas/{empresa_id}/tipos-interacao", response_model=list[CatalogoResponse])
def listar_tipos(empresa_id:UUID,db:Session=Depends(get_db),context=Depends(get_current_context)): return _listar(db,TipoInteracao,empresa_id,context)
@router.post("/empresas/{empresa_id}/tipos-interacao",response_model=CatalogoResponse,status_code=status.HTTP_201_CREATED)
def criar_tipo(empresa_id:UUID,dados:CatalogoCreate,db:Session=Depends(get_db),context=Depends(get_current_context)): return _criar(db,TipoInteracao,empresa_id,dados,context)
@router.put("/tipos-interacao/{obj_id}",response_model=CatalogoResponse)
def editar_tipo(obj_id:UUID,dados:CatalogoUpdate,db:Session=Depends(get_db),context=Depends(get_current_context)): return _editar(db,TipoInteracao,obj_id,dados,context)
@router.patch("/tipos-interacao/{obj_id}/status",response_model=CatalogoResponse)
def status_tipo(obj_id:UUID,dados:CatalogoStatus,db:Session=Depends(get_db),context=Depends(get_current_context)): return _status(db,TipoInteracao,obj_id,dados,context)
