from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_platform_db
from app.models.platform_auth import PlatformProvedorIntegracao, PlatformAplicacaoIntegracao
from app.schemas.platform_integracoes import ProvedorResponse, AplicacaoCreate, AplicacaoUpdate, AplicacaoResponse
from app.security.dependencies import require_platform_admin

router=APIRouter(prefix="/api/platform",tags=["Plataforma - Provedores e Aplicacoes"],dependencies=[Depends(require_platform_admin)])

def _resp(a,p):
    return AplicacaoResponse(id=a.id,provedor_id=a.provedor_id,provedor_codigo=p.codigo,provedor_nome=p.nome,codigo=a.codigo,nome=a.nome,app_id=a.app_id,owner_business_id=a.owner_business_id,embedded_signup_config_id=a.embedded_signup_config_id,graph_api_version=a.graph_api_version,modo=a.modo,status_revisao=a.status_revisao,callback_url=a.callback_url,permissoes=a.permissoes or [],webhook_campos=a.webhook_campos or [],observacoes=a.observacoes,ativo=a.ativo,has_app_secret=bool(a.app_secret_ref),has_access_token=bool(a.access_token_ref),has_verify_token=bool(a.verify_token_ref))

def _commit(db):
    try: db.commit()
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409,detail="Codigo de aplicacao ja utilizado.") from exc

@router.get("/provedores",response_model=list[ProvedorResponse])
def provedores(db:Session=Depends(get_platform_db)):
    return db.query(PlatformProvedorIntegracao).order_by(PlatformProvedorIntegracao.nome).all()

@router.get("/aplicacoes",response_model=list[AplicacaoResponse])
def listar(db:Session=Depends(get_platform_db)):
    rows=db.query(PlatformAplicacaoIntegracao,PlatformProvedorIntegracao).join(PlatformProvedorIntegracao,PlatformProvedorIntegracao.id==PlatformAplicacaoIntegracao.provedor_id).order_by(PlatformProvedorIntegracao.nome,PlatformAplicacaoIntegracao.nome).all()
    return [_resp(a,p) for a,p in rows]

@router.get("/aplicacoes/{app_id}",response_model=AplicacaoResponse)
def consultar(app_id:UUID,db:Session=Depends(get_platform_db)):
    row=db.query(PlatformAplicacaoIntegracao,PlatformProvedorIntegracao).join(PlatformProvedorIntegracao).filter(PlatformAplicacaoIntegracao.id==app_id).first()
    if not row: raise HTTPException(status_code=404,detail="Aplicacao nao encontrada.")
    return _resp(*row)

@router.post("/aplicacoes",response_model=AplicacaoResponse,status_code=status.HTTP_201_CREATED)
def criar(dados:AplicacaoCreate,db:Session=Depends(get_platform_db)):
    p=db.get(PlatformProvedorIntegracao,dados.provedor_id)
    if not p: raise HTTPException(status_code=404,detail="Provedor nao encontrado.")
    item=PlatformAplicacaoIntegracao(id=uuid4(),**dados.model_dump())
    db.add(item); _commit(db); db.refresh(item); return _resp(item,p)

@router.patch("/aplicacoes/{app_id}",response_model=AplicacaoResponse)
def atualizar(app_id:UUID,dados:AplicacaoUpdate,db:Session=Depends(get_platform_db)):
    item=db.get(PlatformAplicacaoIntegracao,app_id)
    if not item: raise HTTPException(status_code=404,detail="Aplicacao nao encontrada.")
    changes=dados.model_dump(exclude_unset=True)
    for campo,valor in changes.items():
        if campo in {"app_secret_ref","access_token_ref","verify_token_ref"} and not valor: continue
        setattr(item,campo,valor)
    _commit(db); db.refresh(item); p=db.get(PlatformProvedorIntegracao,item.provedor_id); return _resp(item,p)
