import re
import unicodedata
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.contato import Contato
from app.models.empresa import Empresa
from app.models.interacao import Interacao
from app.models.manutencao import OrigemContato
from app.schemas.contato_admin import (
    ContatoAdminCreate,
    ContatoAdminResponse,
    ContatoAdminUpdate,
    CriarEmpresaDoContatoRequest,
    VincularEmpresaRequest,
)
from app.schemas.empresa import EmpresaCreate, EmpresaDetalheResponse, EmpresaResponse, EmpresaUpdate
from app.security.dependencies import get_current_context, require_empresa_access


router = APIRouter(
    prefix="/api/admin",
    tags=["Admin - Empresas e Contatos"],
    dependencies=[Depends(get_current_context)],
)

SEM_EMPRESA_SLUG = "sem-empresa"


def _somente_digitos(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return digits or None


def _slug_base(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug[:70] or "empresa"


def _slug_unico(db: Session, nome: str, slug_sugerido: str | None = None, ignorar_id: UUID | None = None) -> str:
    base = _slug_base(slug_sugerido or nome)
    candidato = base
    seq = 2
    while True:
        query = db.query(Empresa.id).filter(Empresa.slug == candidato)
        if ignorar_id is not None:
            query = query.filter(Empresa.id != ignorar_id)
        if query.first() is None:
            return candidato
        candidato = f"{base[:70-len(str(seq))-1]}-{seq}"
        seq += 1


def _empresa_ou_404(db: Session, empresa_id: UUID) -> Empresa:
    empresa = db.query(Empresa).filter(Empresa.id == empresa_id).first()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa não encontrada.")
    return empresa


def _contato_ou_404(db: Session, contato_id: UUID) -> Contato:
    contato = db.query(Contato).filter(Contato.id == contato_id).first()
    if not contato:
        raise HTTPException(status_code=404, detail="Contato não encontrado.")
    return contato


def _sem_empresa(db: Session) -> Empresa:
    empresa = db.query(Empresa).filter(Empresa.slug == SEM_EMPRESA_SLUG).first()
    if not empresa:
        raise HTTPException(
            status_code=500,
            detail="Empresa técnica 'sem-empresa' não encontrada. Execute a migration aprovada antes de usar este módulo.",
        )
    return empresa


def _empresa_por_cnpj(db: Session, cnpj: str | None, ignorar_id: UUID | None = None) -> Empresa | None:
    alvo = _somente_digitos(cnpj)
    if not alvo:
        return None
    # CNPJ ainda não possui índice normalizado no banco; volume atual é pequeno.
    for empresa in db.query(Empresa).filter(Empresa.cnpj.is_not(None)).all():
        if ignorar_id is not None and empresa.id == ignorar_id:
            continue
        if _somente_digitos(empresa.cnpj) == alvo:
            return empresa
    return None


def _contato_response(db: Session, contato: Contato) -> ContatoAdminResponse:
    empresa = db.query(Empresa).filter(Empresa.id == contato.empresa_id).first()
    origem = db.query(OrigemContato).filter(OrigemContato.id == contato.origem_contato_id).first() if contato.origem_contato_id else None
    return ContatoAdminResponse(
        **ContatoAdminResponse.model_validate(contato).model_dump(exclude={"empresa_nome", "origem_contato_nome"}),
        empresa_nome=empresa.nome if empresa else None,
        origem_contato_nome=origem.nome if origem else None,
    )

def _validar_origem(db: Session, origem_id: UUID | None, empresa_id: UUID):
    if origem_id is None: return None
    origem=db.query(OrigemContato).filter(OrigemContato.id==origem_id, OrigemContato.ativo.is_(True)).first()
    if not origem or (origem.empresa_id is not None and origem.empresa_id != empresa_id):
        raise HTTPException(400, "Origem de contato inválida para esta empresa.")
    return origem


def _vincular_contato(db: Session, contato: Contato, empresa: Empresa):
    contato.empresa_id = empresa.id
    # Interações históricas pertencem ao mesmo contato e devem acompanhar seu vínculo empresarial.
    db.query(Interacao).filter(Interacao.contato_id == contato.id).update(
        {Interacao.empresa_id: empresa.id},
        synchronize_session=False,
    )


@router.get("/empresas", response_model=list[EmpresaResponse])
def listar_empresas(
    busca: str | None = Query(default=None, min_length=1),
    status_empresa: str | None = Query(default=None, alias="status"),
    ativo: bool | None = None,
    incluir_sem_empresa: bool = True,
    db: Session = Depends(get_db),
    context=Depends(get_current_context),
):
    query = db.query(Empresa)
    if not context["usuario"].is_superadmin:
        if not context.get("empresa_id"):
            return []
        query = query.filter(Empresa.id == context["empresa_id"])
    if busca:
        termo = f"%{busca.strip()}%"
        query = query.filter(
            or_(
                Empresa.nome.ilike(termo),
                Empresa.cnpj.ilike(termo),
                Empresa.dominio.ilike(termo),
                Empresa.email.ilike(termo),
            )
        )
    if status_empresa:
        query = query.filter(Empresa.status == status_empresa.upper())
    if ativo is not None:
        query = query.filter(Empresa.ativo == ativo)
    if not incluir_sem_empresa:
        query = query.filter(Empresa.slug != SEM_EMPRESA_SLUG)
    return query.order_by(Empresa.nome).all()


@router.post("/empresas", response_model=EmpresaResponse, status_code=status.HTTP_201_CREATED)
def criar_empresa(dados: EmpresaCreate, db: Session = Depends(get_db), context=Depends(get_current_context)):
    if not context["usuario"].is_superadmin:
        raise HTTPException(status_code=403, detail="Somente administrador MDP pode criar empresas/tenants.")
    duplicada_cnpj = _empresa_por_cnpj(db, dados.cnpj)
    if duplicada_cnpj:
        raise HTTPException(status_code=409, detail=f"Já existe empresa com este CNPJ: {duplicada_cnpj.nome}.")

    payload = dados.model_dump()
    payload["slug"] = _slug_unico(db, dados.nome, dados.slug)
    empresa = Empresa(**payload)
    db.add(empresa)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflito ao criar empresa.")
    db.refresh(empresa)
    return empresa


@router.get("/empresas/{empresa_id}", response_model=EmpresaDetalheResponse)
def obter_empresa(empresa_id: UUID, db: Session = Depends(get_db), context=Depends(get_current_context)):
    require_empresa_access(context, empresa_id)
    empresa = _empresa_ou_404(db, empresa_id)
    total_contatos = db.query(func.count(Contato.id)).filter(Contato.empresa_id == empresa.id).scalar() or 0
    return EmpresaDetalheResponse(
        **EmpresaResponse.model_validate(empresa).model_dump(),
        total_contatos=total_contatos,
    )


@router.put("/empresas/{empresa_id}", response_model=EmpresaResponse)
def atualizar_empresa(empresa_id: UUID, dados: EmpresaUpdate, db: Session = Depends(get_db), context=Depends(get_current_context)):
    require_empresa_access(context, empresa_id)
    empresa = _empresa_ou_404(db, empresa_id)
    alteracoes = dados.model_dump(exclude_unset=True)

    if "cnpj" in alteracoes:
        duplicada = _empresa_por_cnpj(db, alteracoes.get("cnpj"), ignorar_id=empresa.id)
        if duplicada:
            raise HTTPException(status_code=409, detail=f"Já existe empresa com este CNPJ: {duplicada.nome}.")

    if "slug" in alteracoes:
        alteracoes["slug"] = _slug_unico(db, alteracoes.get("nome") or empresa.nome, alteracoes.get("slug"), ignorar_id=empresa.id)

    for campo, valor in alteracoes.items():
        setattr(empresa, campo, valor)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflito ao atualizar empresa.")
    db.refresh(empresa)
    return empresa


@router.delete("/empresas/{empresa_id}", response_model=EmpresaResponse)
def inativar_empresa(empresa_id: UUID, db: Session = Depends(get_db), context=Depends(get_current_context)):
    require_empresa_access(context, empresa_id)
    empresa = _empresa_ou_404(db, empresa_id)
    if empresa.slug == SEM_EMPRESA_SLUG:
        raise HTTPException(status_code=409, detail="A empresa técnica 'sem-empresa' não pode ser inativada.")
    empresa.ativo = False
    db.commit()
    db.refresh(empresa)
    return empresa


@router.get("/empresas/{empresa_id}/contatos", response_model=list[ContatoAdminResponse])
def listar_contatos_empresa(empresa_id: UUID, db: Session = Depends(get_db), context=Depends(get_current_context)):
    require_empresa_access(context, empresa_id)
    _empresa_ou_404(db, empresa_id)
    contatos = db.query(Contato).filter(Contato.empresa_id == empresa_id).order_by(Contato.nome).all()
    return [_contato_response(db, c) for c in contatos]


@router.get("/contatos", response_model=list[ContatoAdminResponse])
def listar_contatos(
    busca: str | None = Query(default=None, min_length=1),
    empresa_id: UUID | None = None,
    status_contato: str | None = Query(default=None, alias="status"),
    tipo_solicitacao: str | None = None,
    origem: str | None = None,
    db: Session = Depends(get_db),
    context=Depends(get_current_context),
):
    query = db.query(Contato)
    if not context["usuario"].is_superadmin:
        if not context.get("empresa_id"):
            return []
        if empresa_id and empresa_id != context["empresa_id"]:
            raise HTTPException(status_code=403, detail="Acesso negado à empresa informada.")
        query = query.filter(Contato.empresa_id == context["empresa_id"])
    if busca:
        termo = f"%{busca.strip()}%"
        query = query.filter(
            or_(
                Contato.nome.ilike(termo),
                Contato.email.ilike(termo),
                Contato.telefone.ilike(termo),
                Contato.cnpj.ilike(termo),
                Contato.empresa_contato.ilike(termo),
            )
        )
    if empresa_id:
        query = query.filter(Contato.empresa_id == empresa_id)
    if status_contato:
        query = query.filter(func.upper(Contato.status) == status_contato.upper())
    if tipo_solicitacao:
        query = query.filter(Contato.tipo_solicitacao == tipo_solicitacao.upper())
    if origem:
        query = query.filter(func.upper(Contato.origem) == origem.upper())
    contatos = query.order_by(Contato.created_at.desc(), Contato.nome).all()
    return [_contato_response(db, c) for c in contatos]


@router.post("/contatos", response_model=ContatoAdminResponse, status_code=status.HTTP_201_CREATED)
def criar_contato_admin(dados: ContatoAdminCreate, db: Session = Depends(get_db), context=Depends(get_current_context)):
    alvo_empresa_id = dados.empresa_id or (_sem_empresa(db).id if context["usuario"].is_superadmin else context.get("empresa_id"))
    if alvo_empresa_id is None:
        raise HTTPException(status_code=403, detail="Empresa ativa não definida.")
    require_empresa_access(context, alvo_empresa_id)
    empresa = _empresa_ou_404(db, alvo_empresa_id)
    payload = dados.model_dump(exclude={"empresa_id"})
    payload["empresa_id"] = empresa.id
    origem_obj = _validar_origem(db, dados.origem_contato_id, empresa.id)
    if origem_obj: payload["origem"] = origem_obj.codigo
    payload["origem_primeiro_contato"] = payload["origem"]
    payload["origem_ultimo_contato"] = payload["origem"]
    payload["consentimento_dados"] = False
    contato = Contato(**payload)
    db.add(contato)
    db.commit()
    db.refresh(contato)
    return _contato_response(db, contato)


@router.get("/contatos/{contato_id}", response_model=ContatoAdminResponse)
def obter_contato(contato_id: UUID, db: Session = Depends(get_db), context=Depends(get_current_context)):
    contato = _contato_ou_404(db, contato_id)
    require_empresa_access(context, contato.empresa_id)
    return _contato_response(db, contato)


@router.put("/contatos/{contato_id}", response_model=ContatoAdminResponse)
def atualizar_contato(contato_id: UUID, dados: ContatoAdminUpdate, db: Session = Depends(get_db), context=Depends(get_current_context)):
    contato = _contato_ou_404(db, contato_id)
    require_empresa_access(context, contato.empresa_id)
    payload = dados.model_dump(exclude_unset=True)
    if "origem_contato_id" in payload:
        origem_obj = _validar_origem(db, payload.get("origem_contato_id"), contato.empresa_id)
        if origem_obj:
            payload["origem"] = origem_obj.codigo
            payload["origem_ultimo_contato"] = origem_obj.codigo
    for campo, valor in payload.items():
        setattr(contato, campo, valor)
    db.commit()
    db.refresh(contato)
    return _contato_response(db, contato)


@router.delete("/contatos/{contato_id}", response_model=ContatoAdminResponse)
def descartar_contato(contato_id: UUID, db: Session = Depends(get_db), context=Depends(get_current_context)):
    contato = _contato_ou_404(db, contato_id)
    require_empresa_access(context, contato.empresa_id)
    contato.status = "DESCARTADO"
    db.commit()
    db.refresh(contato)
    return _contato_response(db, contato)


@router.put("/contatos/{contato_id}/empresa", response_model=ContatoAdminResponse)
def vincular_empresa(contato_id: UUID, dados: VincularEmpresaRequest, db: Session = Depends(get_db), context=Depends(get_current_context)):
    contato = _contato_ou_404(db, contato_id)
    require_empresa_access(context, contato.empresa_id)
    require_empresa_access(context, dados.empresa_id)
    empresa = _empresa_ou_404(db, dados.empresa_id)
    if not empresa.ativo:
        raise HTTPException(status_code=409, detail="Não é possível vincular o contato a uma empresa inativa.")
    _vincular_contato(db, contato, empresa)
    db.commit()
    db.refresh(contato)
    return _contato_response(db, contato)


@router.post("/contatos/{contato_id}/criar-empresa", response_model=ContatoAdminResponse, status_code=status.HTTP_201_CREATED)
def criar_empresa_a_partir_do_contato(
    contato_id: UUID,
    dados: CriarEmpresaDoContatoRequest,
    db: Session = Depends(get_db),
    context=Depends(get_current_context),
):
    if not context["usuario"].is_superadmin:
        raise HTTPException(status_code=403, detail="Somente administrador MDP pode criar empresa a partir de contato.")
    contato = _contato_ou_404(db, contato_id)
    nome = (dados.nome or contato.empresa_contato or "").strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome da empresa.")

    cnpj = dados.cnpj if dados.cnpj is not None else contato.cnpj
    duplicada = _empresa_por_cnpj(db, cnpj)
    if duplicada:
        raise HTTPException(
            status_code=409,
            detail=f"Já existe empresa com este CNPJ: {duplicada.nome}. Use a ação de vincular empresa existente.",
        )

    empresa = Empresa(
        nome=nome,
        slug=_slug_unico(db, nome, dados.slug),
        cnpj=cnpj,
        email=str(dados.email) if dados.email is not None else contato.email,
        telefone=dados.telefone if dados.telefone is not None else contato.telefone,
        dominio=dados.dominio,
        status=dados.status,
        ativo=True,
    )
    db.add(empresa)
    db.flush()
    _vincular_contato(db, contato, empresa)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflito ao criar empresa a partir do contato.")

    db.refresh(contato)
    return _contato_response(db, contato)
