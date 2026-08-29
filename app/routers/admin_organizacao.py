from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import PerfilPermissao, UsuarioEmpresa
from app.models.empresa import Empresa
from app.models.organizacao import Area, TipoUnidade, UnidadeEmpresa, UsuarioArea, UsuarioUnidade
from app.schemas.organizacao import (
    AreaCreate, AreaResponse, AreaUpdate, EscopoUsuarioUpdate, StatusUpdate,
    TipoUnidadeCreate, TipoUnidadeResponse, TipoUnidadeUpdate,
    UnidadeCreate, UnidadeResponse, UnidadeUpdate, VinculoAreaCreate, VinculoUnidadeCreate,
)
from app.security.dependencies import get_current_context, require_area_access, require_empresa_access, require_unidade_access

router = APIRouter(prefix="/api/admin", tags=["Admin - Organização"])


def _commit(db: Session, detail="Conflito de integridade nos dados."):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=detail)


def _require_scope_management(db: Session, context: dict, empresa_id: UUID):
    """Exige autorização administrativa para alterar escopo/vínculos de usuários.

    Superadmin sempre pode. Para administradores do tenant, a permissão explícita
    `usuarios.gerenciar` é obrigatória. Usuários comuns (ex.: ANALISTA) não podem
    elevar o próprio escopo nem atribuir unidade/área a si mesmos ou a terceiros.
    """
    require_empresa_access(context, empresa_id)
    if context["usuario"].is_superadmin:
        return
    vinculo = context.get("vinculo")
    if not vinculo:
        raise HTTPException(status_code=403, detail="Empresa ativa não definida.")
    permitido = db.query(PerfilPermissao.id).join(PerfilPermissao.permissao).filter(
        PerfilPermissao.perfil_id == vinculo.perfil_id,
        PerfilPermissao.permissao.has(codigo="usuarios.gerenciar", ativo=True),
    ).first()
    if not permitido:
        raise HTTPException(status_code=403, detail="Permissão insuficiente para gerenciar escopo de usuários.")


def _empresa(db, empresa_id):
    obj = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not obj:
        raise HTTPException(404, "Empresa não encontrada.")
    return obj


def _tipo_valido(db, empresa_id, tipo_id):
    tipo = db.query(TipoUnidade).filter(TipoUnidade.id == tipo_id).first()
    if not tipo:
        raise HTTPException(404, "Tipo de unidade não encontrado.")
    if tipo.empresa_id is not None and tipo.empresa_id != empresa_id:
        raise HTTPException(409, "Tipo de unidade pertence a outra empresa.")
    if not tipo.ativo:
        raise HTTPException(409, "Tipo de unidade está inativo.")
    return tipo


def _unidade_da_empresa(db, empresa_id, unidade_id):
    unidade = db.query(UnidadeEmpresa).filter(UnidadeEmpresa.id == unidade_id).first()
    if not unidade:
        raise HTTPException(404, "Unidade não encontrada.")
    if unidade.empresa_id != empresa_id:
        raise HTTPException(409, "Unidade pertence a outra empresa.")
    return unidade


def _area_da_empresa(db, empresa_id, area_id):
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(404, "Área não encontrada.")
    if area.empresa_id != empresa_id:
        raise HTTPException(409, "Área pertence a outra empresa.")
    return area


@router.get("/empresas/{empresa_id}/tipos-unidade", response_model=list[TipoUnidadeResponse])
def listar_tipos(empresa_id: UUID, ativo: bool | None = None, db: Session = Depends(get_db), context=Depends(get_current_context)):
    _empresa(db, empresa_id); require_empresa_access(context, empresa_id)
    q = db.query(TipoUnidade).filter((TipoUnidade.empresa_id.is_(None)) | (TipoUnidade.empresa_id == empresa_id))
    if ativo is not None: q = q.filter(TipoUnidade.ativo == ativo)
    return q.order_by(TipoUnidade.ordem, TipoUnidade.nome).all()


@router.post("/empresas/{empresa_id}/tipos-unidade", response_model=TipoUnidadeResponse, status_code=201)
def criar_tipo(empresa_id: UUID, dados: TipoUnidadeCreate, db: Session = Depends(get_db), context=Depends(get_current_context)):
    _empresa(db, empresa_id); require_empresa_access(context, empresa_id)
    obj = TipoUnidade(empresa_id=empresa_id, padrao_sistema=False, **dados.model_dump())
    db.add(obj); _commit(db, "Já existe tipo de unidade com este código nesta empresa."); db.refresh(obj); return obj


@router.put("/tipos-unidade/{tipo_id}", response_model=TipoUnidadeResponse)
def atualizar_tipo(tipo_id: UUID, dados: TipoUnidadeUpdate, db: Session = Depends(get_db), context=Depends(get_current_context)):
    obj = db.query(TipoUnidade).filter(TipoUnidade.id == tipo_id).first()
    if not obj: raise HTTPException(404, "Tipo de unidade não encontrado.")
    if obj.padrao_sistema: raise HTTPException(409, "Tipo padrão MDP é protegido.")
    require_empresa_access(context, obj.empresa_id)
    for k,v in dados.model_dump(exclude_unset=True).items(): setattr(obj,k,v)
    _commit(db); db.refresh(obj); return obj


@router.patch("/tipos-unidade/{tipo_id}/status", response_model=TipoUnidadeResponse)
def status_tipo(tipo_id: UUID, dados: StatusUpdate, db: Session = Depends(get_db), context=Depends(get_current_context)):
    obj = db.query(TipoUnidade).filter(TipoUnidade.id == tipo_id).first()
    if not obj: raise HTTPException(404, "Tipo de unidade não encontrado.")
    if obj.padrao_sistema and not context["usuario"].is_superadmin: raise HTTPException(409, "Tipo padrão MDP é protegido.")
    if obj.empresa_id: require_empresa_access(context, obj.empresa_id)
    elif not context["usuario"].is_superadmin: raise HTTPException(403, "Somente MDP pode alterar tipo global.")
    obj.ativo=dados.ativo; db.commit(); db.refresh(obj); return obj


@router.get("/empresas/{empresa_id}/unidades", response_model=list[UnidadeResponse])
def listar_unidades(empresa_id: UUID, ativo: bool | None=None, db: Session=Depends(get_db), context=Depends(get_current_context)):
    _empresa(db, empresa_id); require_empresa_access(context, empresa_id)
    q=db.query(UnidadeEmpresa).filter(UnidadeEmpresa.empresa_id==empresa_id)
    if not context["usuario"].is_superadmin and not context["vinculo"].acesso_todas_unidades:
        q=q.join(UsuarioUnidade, UsuarioUnidade.unidade_id==UnidadeEmpresa.id).filter(UsuarioUnidade.usuario_empresa_id==context["vinculo"].id)
    if ativo is not None: q=q.filter(UnidadeEmpresa.ativo==ativo)
    return q.order_by(UnidadeEmpresa.nome).all()


@router.post("/empresas/{empresa_id}/unidades", response_model=UnidadeResponse, status_code=201)
def criar_unidade(empresa_id: UUID, dados: UnidadeCreate, db: Session=Depends(get_db), context=Depends(get_current_context)):
    _empresa(db, empresa_id); require_empresa_access(context, empresa_id); _tipo_valido(db, empresa_id, dados.tipo_unidade_id)
    obj=UnidadeEmpresa(empresa_id=empresa_id, **dados.model_dump()); db.add(obj); _commit(db, "Código ou CNPJ de unidade já utilizado."); db.refresh(obj); return obj


@router.get("/unidades/{unidade_id}", response_model=UnidadeResponse)
def obter_unidade(unidade_id: UUID, db: Session=Depends(get_db), context=Depends(get_current_context)):
    obj=db.query(UnidadeEmpresa).filter(UnidadeEmpresa.id==unidade_id).first()
    if not obj: raise HTTPException(404,"Unidade não encontrada.")
    require_empresa_access(context,obj.empresa_id)
    if not context["usuario"].is_superadmin and not context["vinculo"].acesso_todas_unidades:
        if not db.query(UsuarioUnidade.id).filter(UsuarioUnidade.usuario_empresa_id==context["vinculo"].id, UsuarioUnidade.unidade_id==obj.id).first(): raise HTTPException(403,"Usuário sem acesso a esta unidade.")
    return obj


@router.put("/unidades/{unidade_id}", response_model=UnidadeResponse)
def atualizar_unidade(unidade_id: UUID, dados: UnidadeUpdate, db: Session=Depends(get_db), context=Depends(get_current_context)):
    obj=db.query(UnidadeEmpresa).filter(UnidadeEmpresa.id==unidade_id).first()
    if not obj: raise HTTPException(404,"Unidade não encontrada.")
    obj = require_unidade_access(db, context, unidade_id)
    changes=dados.model_dump(exclude_unset=True)
    if "tipo_unidade_id" in changes: _tipo_valido(db,obj.empresa_id,changes["tipo_unidade_id"])
    for k,v in changes.items(): setattr(obj,k,v)
    _commit(db,"Código ou CNPJ de unidade já utilizado."); db.refresh(obj); return obj


@router.patch("/unidades/{unidade_id}/status", response_model=UnidadeResponse)
def status_unidade(unidade_id: UUID, dados: StatusUpdate, db: Session=Depends(get_db), context=Depends(get_current_context)):
    obj=db.query(UnidadeEmpresa).filter(UnidadeEmpresa.id==unidade_id).first()
    if not obj: raise HTTPException(404,"Unidade não encontrada.")
    obj = require_unidade_access(db, context, unidade_id)
    obj.ativo=dados.ativo; db.commit(); db.refresh(obj); return obj


@router.get("/empresas/{empresa_id}/areas", response_model=list[AreaResponse])
def listar_areas(empresa_id: UUID, unidade_id: UUID | None=None, ativo: bool | None=None, db: Session=Depends(get_db), context=Depends(get_current_context)):
    _empresa(db,empresa_id); require_empresa_access(context,empresa_id)
    q=db.query(Area).filter(Area.empresa_id==empresa_id)
    if unidade_id is not None: q=q.filter(Area.unidade_id==unidade_id)
    if not context["usuario"].is_superadmin and not context["vinculo"].acesso_todas_areas:
        q=q.join(UsuarioArea,UsuarioArea.area_id==Area.id).filter(UsuarioArea.usuario_empresa_id==context["vinculo"].id)
    if ativo is not None: q=q.filter(Area.ativo==ativo)
    return q.order_by(Area.ordem,Area.nome).all()


@router.post("/empresas/{empresa_id}/areas", response_model=AreaResponse, status_code=201)
def criar_area(empresa_id: UUID, dados: AreaCreate, db: Session=Depends(get_db), context=Depends(get_current_context)):
    _empresa(db,empresa_id); require_empresa_access(context,empresa_id)
    if dados.unidade_id: _unidade_da_empresa(db,empresa_id,dados.unidade_id)
    obj=Area(empresa_id=empresa_id,**dados.model_dump()); db.add(obj); _commit(db,"Código ou ordem da área já utilizado neste escopo."); db.refresh(obj); return obj


@router.get("/areas/{area_id}", response_model=AreaResponse)
def obter_area(area_id: UUID, db: Session=Depends(get_db), context=Depends(get_current_context)):
    obj=db.query(Area).filter(Area.id==area_id).first()
    if not obj: raise HTTPException(404,"Área não encontrada.")
    require_empresa_access(context,obj.empresa_id)
    if not context["usuario"].is_superadmin and not context["vinculo"].acesso_todas_areas:
        if not db.query(UsuarioArea.id).filter(UsuarioArea.usuario_empresa_id==context["vinculo"].id,UsuarioArea.area_id==obj.id).first(): raise HTTPException(403,"Usuário sem acesso a esta área.")
    return obj


@router.put("/areas/{area_id}", response_model=AreaResponse)
def atualizar_area(area_id: UUID, dados: AreaUpdate, db: Session=Depends(get_db), context=Depends(get_current_context)):
    obj=db.query(Area).filter(Area.id==area_id).first()
    if not obj: raise HTTPException(404,"Área não encontrada.")
    obj = require_area_access(db, context, area_id)
    changes=dados.model_dump(exclude_unset=True)
    if "unidade_id" in changes and changes["unidade_id"]: _unidade_da_empresa(db,obj.empresa_id,changes["unidade_id"])
    for k,v in changes.items(): setattr(obj,k,v)
    _commit(db,"Código ou ordem da área já utilizado neste escopo."); db.refresh(obj); return obj


@router.patch("/areas/{area_id}/status", response_model=AreaResponse)
def status_area(area_id: UUID, dados: StatusUpdate, db: Session=Depends(get_db), context=Depends(get_current_context)):
    obj=db.query(Area).filter(Area.id==area_id).first()
    if not obj: raise HTTPException(404,"Área não encontrada.")
    obj = require_area_access(db, context, area_id)
    obj.ativo=dados.ativo; db.commit(); db.refresh(obj); return obj


@router.patch("/usuarios-empresas/{vinculo_id}/escopo")
def atualizar_escopo(vinculo_id: UUID, dados: EscopoUsuarioUpdate, db: Session=Depends(get_db), context=Depends(get_current_context)):
    vinc=db.query(UsuarioEmpresa).filter(UsuarioEmpresa.id==vinculo_id).first()
    if not vinc: raise HTTPException(404,"Vínculo usuário/empresa não encontrado.")
    _require_scope_management(db, context, vinc.empresa_id)
    for k,v in dados.model_dump(exclude_unset=True).items(): setattr(vinc,k,v)
    db.commit(); return {"status":"ok","usuario_empresa_id":vinc.id,"acesso_todas_unidades":vinc.acesso_todas_unidades,"acesso_todas_areas":vinc.acesso_todas_areas}


@router.post("/usuarios-empresas/{vinculo_id}/unidades", status_code=201)
def vincular_unidade(vinculo_id: UUID, dados: VinculoUnidadeCreate, db: Session=Depends(get_db), context=Depends(get_current_context)):
    vinc=db.query(UsuarioEmpresa).filter(UsuarioEmpresa.id==vinculo_id).first()
    if not vinc: raise HTTPException(404,"Vínculo usuário/empresa não encontrado.")
    _require_scope_management(db, context, vinc.empresa_id); unidade=_unidade_da_empresa(db,vinc.empresa_id,dados.unidade_id)
    if not unidade.ativo: raise HTTPException(409,"Unidade está inativa.")
    obj=UsuarioUnidade(usuario_empresa_id=vinc.id,unidade_id=unidade.id); db.add(obj); _commit(db,"Usuário já possui vínculo com esta unidade."); return {"status":"ok"}


@router.delete("/usuarios-empresas/{vinculo_id}/unidades/{unidade_id}")
def desvincular_unidade(vinculo_id: UUID, unidade_id: UUID, db: Session=Depends(get_db), context=Depends(get_current_context)):
    vinc=db.query(UsuarioEmpresa).filter(UsuarioEmpresa.id==vinculo_id).first()
    if not vinc: raise HTTPException(404,"Vínculo usuário/empresa não encontrado.")
    _require_scope_management(db, context, vinc.empresa_id); _unidade_da_empresa(db,vinc.empresa_id,unidade_id)
    db.query(UsuarioUnidade).filter(UsuarioUnidade.usuario_empresa_id==vinc.id,UsuarioUnidade.unidade_id==unidade_id).delete(); db.commit(); return {"status":"ok"}


@router.post("/usuarios-empresas/{vinculo_id}/areas", status_code=201)
def vincular_area(vinculo_id: UUID, dados: VinculoAreaCreate, db: Session=Depends(get_db), context=Depends(get_current_context)):
    vinc=db.query(UsuarioEmpresa).filter(UsuarioEmpresa.id==vinculo_id).first()
    if not vinc: raise HTTPException(404,"Vínculo usuário/empresa não encontrado.")
    _require_scope_management(db, context, vinc.empresa_id); area=_area_da_empresa(db,vinc.empresa_id,dados.area_id)
    if not area.ativo: raise HTTPException(409,"Área está inativa.")
    obj=UsuarioArea(usuario_empresa_id=vinc.id,area_id=area.id); db.add(obj); _commit(db,"Usuário já possui vínculo com esta área."); return {"status":"ok"}


@router.delete("/usuarios-empresas/{vinculo_id}/areas/{area_id}")
def desvincular_area(vinculo_id: UUID, area_id: UUID, db: Session=Depends(get_db), context=Depends(get_current_context)):
    vinc=db.query(UsuarioEmpresa).filter(UsuarioEmpresa.id==vinculo_id).first()
    if not vinc: raise HTTPException(404,"Vínculo usuário/empresa não encontrado.")
    _require_scope_management(db, context, vinc.empresa_id); _area_da_empresa(db,vinc.empresa_id,area_id)
    db.query(UsuarioArea).filter(UsuarioArea.usuario_empresa_id==vinc.id,UsuarioArea.area_id==area_id).delete(); db.commit(); return {"status":"ok"}
