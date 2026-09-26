from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.empresa import Empresa
from app.models.tipo_organizacao import EmpresaTipoOrganizacao, TipoOrganizacao
from app.schemas.tipo_organizacao import TipoOrganizacaoCreate, TipoOrganizacaoResponse, TipoOrganizacaoUpdate, TiposEmpresaUpdate
from app.security.dependencies import get_current_context, require_empresa_access


router = APIRouter(prefix="/api/admin", tags=["Admin - Tipos de Organização"], dependencies=[Depends(get_current_context)])


def _require_admin(context):
    if context["usuario"].is_superadmin:
        return
    vinculo = context.get("vinculo")
    if not vinculo or not vinculo.perfil.acesso_total:
        raise HTTPException(status_code=403, detail="Somente administrador do Tenant pode manter tipos de organização.")


def _tipo_ou_404(db: Session, tipo_id: UUID):
    obj = db.query(TipoOrganizacao).filter(TipoOrganizacao.id == tipo_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Tipo de organização não encontrado.")
    return obj


@router.get("/tipos-organizacao", response_model=list[TipoOrganizacaoResponse])
def listar_tipos_organizacao(db: Session = Depends(get_db), context=Depends(get_current_context)):
    _require_admin(context)
    return db.query(TipoOrganizacao).order_by(TipoOrganizacao.ordem, TipoOrganizacao.nome).all()


@router.post("/tipos-organizacao", response_model=TipoOrganizacaoResponse, status_code=status.HTTP_201_CREATED)
def criar_tipo_organizacao(dados: TipoOrganizacaoCreate, db: Session = Depends(get_db), context=Depends(get_current_context)):
    _require_admin(context)
    ordem = dados.ordem or ((db.query(func.max(TipoOrganizacao.ordem)).scalar() or 0) + 1)
    obj = TipoOrganizacao(codigo=dados.codigo, nome=dados.nome.strip(), descricao=dados.descricao, ordem=ordem, ativo=dados.ativo, padrao_sistema=False)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Código ou ordem já cadastrado para tipo de organização.")
    db.refresh(obj)
    return obj


@router.put("/tipos-organizacao/{tipo_id}", response_model=TipoOrganizacaoResponse)
def atualizar_tipo_organizacao(tipo_id: UUID, dados: TipoOrganizacaoUpdate, db: Session = Depends(get_db), context=Depends(get_current_context)):
    _require_admin(context)
    obj = _tipo_ou_404(db, tipo_id)
    vals = dados.model_dump(exclude_unset=True)
    if "nome" in vals and vals["nome"] is not None:
        vals["nome"] = vals["nome"].strip()
    for campo, valor in vals.items():
        setattr(obj, campo, valor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Código ou ordem já cadastrado para tipo de organização.")
    db.refresh(obj)
    return obj


@router.get("/empresas/{empresa_id}/tipos-organizacao", response_model=list[TipoOrganizacaoResponse])
def listar_tipos_empresa(empresa_id: UUID, db: Session = Depends(get_db), context=Depends(get_current_context)):
    require_empresa_access(context, empresa_id)
    if not db.query(Empresa.id).filter(Empresa.id == empresa_id).first():
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    return (
        db.query(TipoOrganizacao)
        .join(EmpresaTipoOrganizacao, EmpresaTipoOrganizacao.tipo_organizacao_id == TipoOrganizacao.id)
        .filter(EmpresaTipoOrganizacao.empresa_id == empresa_id)
        .order_by(TipoOrganizacao.ordem, TipoOrganizacao.nome)
        .all()
    )


@router.put("/empresas/{empresa_id}/tipos-organizacao", response_model=list[TipoOrganizacaoResponse])
def substituir_tipos_empresa(empresa_id: UUID, dados: TiposEmpresaUpdate, db: Session = Depends(get_db), context=Depends(get_current_context)):
    require_empresa_access(context, empresa_id)
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    if empresa.organizacao_principal and dados.tipo_ids:
        raise HTTPException(status_code=409, detail="A organização principal do Tenant não pode possuir tipos de relacionamento.")

    ids = list(dict.fromkeys(dados.tipo_ids))
    if ids:
        tipos = db.query(TipoOrganizacao).filter(TipoOrganizacao.id.in_(ids), TipoOrganizacao.ativo.is_(True)).all()
        if len(tipos) != len(ids):
            raise HTTPException(status_code=400, detail="Há tipo de organização inexistente ou inativo na seleção.")

    db.query(EmpresaTipoOrganizacao).filter(EmpresaTipoOrganizacao.empresa_id == empresa_id).delete(synchronize_session=False)
    for tipo_id in ids:
        db.add(EmpresaTipoOrganizacao(empresa_id=empresa_id, tipo_organizacao_id=tipo_id))
    db.commit()

    return listar_tipos_empresa(empresa_id, db, context)
