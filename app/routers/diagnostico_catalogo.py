from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.security.dependencies import get_current_context
from app.models.diagnostico import (
    CategoriaDiagnostico,
    OpcaoPerguntaDiagnostico,
    PerguntaDiagnostico,
)
from app.schemas.diagnostico import (
    CategoriaCreate,
    CategoriaResponse,
    CategoriaUpdate,
    OpcaoCreate,
    OpcaoResponse,
    OpcaoUpdate,
    PerguntaCreate,
    PerguntaDetalheResponse,
    PerguntaResponse,
    PerguntaUpdate,
)

router = APIRouter(
    prefix="/api/diagnostico",
    tags=["Diagnóstico - Catálogo"],
    dependencies=[Depends(get_current_context)],
)


def _categoria_ou_404(db: Session, categoria_id: UUID) -> CategoriaDiagnostico:
    categoria = db.query(CategoriaDiagnostico).filter(CategoriaDiagnostico.id == categoria_id).first()
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada.")
    return categoria


def _pergunta_ou_404(db: Session, pergunta_id: UUID) -> PerguntaDiagnostico:
    pergunta = db.query(PerguntaDiagnostico).filter(PerguntaDiagnostico.id == pergunta_id).first()
    if not pergunta:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada.")
    return pergunta


def _opcao_ou_404(db: Session, opcao_id: UUID) -> OpcaoPerguntaDiagnostico:
    opcao = db.query(OpcaoPerguntaDiagnostico).filter(OpcaoPerguntaDiagnostico.id == opcao_id).first()
    if not opcao:
        raise HTTPException(status_code=404, detail="Opção não encontrada.")
    return opcao


@router.get("/categorias", response_model=list[CategoriaResponse])
def listar_categorias(
    ativo: bool | None = None,
    empresa_id: UUID | None = None,
    incluir_globais: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(CategoriaDiagnostico)

    if empresa_id is not None:
        if incluir_globais:
            query = query.filter(
                or_(
                    CategoriaDiagnostico.empresa_id == empresa_id,
                    CategoriaDiagnostico.empresa_id.is_(None),
                )
            )
        else:
            query = query.filter(CategoriaDiagnostico.empresa_id == empresa_id)
    elif not incluir_globais:
        query = query.filter(CategoriaDiagnostico.empresa_id.is_not(None))

    if ativo is not None:
        query = query.filter(CategoriaDiagnostico.ativo == ativo)

    return query.order_by(CategoriaDiagnostico.ordem, CategoriaDiagnostico.nome).all()


@router.post(
    "/categorias",
    response_model=CategoriaResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_categoria(dados: CategoriaCreate, db: Session = Depends(get_db)):
    existente = (
        db.query(CategoriaDiagnostico)
        .filter(
            CategoriaDiagnostico.empresa_id.is_(None)
            if dados.empresa_id is None
            else CategoriaDiagnostico.empresa_id == dados.empresa_id,
            CategoriaDiagnostico.nome.ilike(dados.nome.strip()),
        )
        .first()
    )
    if existente:
        raise HTTPException(status_code=409, detail="Já existe categoria com esse nome.")

    categoria = CategoriaDiagnostico(**dados.model_dump())
    categoria.nome = categoria.nome.strip()
    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    return categoria


@router.get("/categorias/{categoria_id}", response_model=CategoriaResponse)
def obter_categoria(categoria_id: UUID, db: Session = Depends(get_db)):
    return _categoria_ou_404(db, categoria_id)


@router.put("/categorias/{categoria_id}", response_model=CategoriaResponse)
def atualizar_categoria(
    categoria_id: UUID,
    dados: CategoriaUpdate,
    db: Session = Depends(get_db),
):
    categoria = _categoria_ou_404(db, categoria_id)
    alteracoes = dados.model_dump(exclude_unset=True)
    for campo, valor in alteracoes.items():
        if campo == "nome" and valor is not None:
            valor = valor.strip()
        setattr(categoria, campo, valor)

    db.commit()
    db.refresh(categoria)
    return categoria


@router.delete("/categorias/{categoria_id}", response_model=CategoriaResponse)
def desativar_categoria(categoria_id: UUID, db: Session = Depends(get_db)):
    categoria = _categoria_ou_404(db, categoria_id)
    categoria.ativo = False
    db.commit()
    db.refresh(categoria)
    return categoria


@router.get("/perguntas", response_model=list[PerguntaResponse])
def listar_perguntas(
    categoria_id: UUID | None = None,
    ativo: bool | None = None,
    tipo_resposta: str | None = None,
    busca: str | None = Query(default=None, min_length=1),
    empresa_id: UUID | None = None,
    incluir_globais: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(PerguntaDiagnostico)

    if categoria_id:
        query = query.filter(PerguntaDiagnostico.categoria_id == categoria_id)
    if ativo is not None:
        query = query.filter(PerguntaDiagnostico.ativo == ativo)
    if tipo_resposta:
        query = query.filter(PerguntaDiagnostico.tipo_resposta == tipo_resposta)
    if busca:
        termo = f"%{busca.strip()}%"
        query = query.filter(
            or_(
                PerguntaDiagnostico.codigo.ilike(termo),
                PerguntaDiagnostico.pergunta.ilike(termo),
            )
        )

    if empresa_id is not None:
        if incluir_globais:
            query = query.filter(
                or_(
                    PerguntaDiagnostico.empresa_id == empresa_id,
                    PerguntaDiagnostico.empresa_id.is_(None),
                )
            )
        else:
            query = query.filter(PerguntaDiagnostico.empresa_id == empresa_id)
    elif not incluir_globais:
        query = query.filter(PerguntaDiagnostico.empresa_id.is_not(None))

    return query.order_by(PerguntaDiagnostico.ordem, PerguntaDiagnostico.codigo).all()


@router.post(
    "/perguntas",
    response_model=PerguntaDetalheResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_pergunta(dados: PerguntaCreate, db: Session = Depends(get_db)):
    categoria = _categoria_ou_404(db, dados.categoria_id)

    if dados.codigo:
        existente = (
            db.query(PerguntaDiagnostico)
            .filter(
                PerguntaDiagnostico.empresa_id.is_(None)
                if dados.empresa_id is None
                else PerguntaDiagnostico.empresa_id == dados.empresa_id,
                PerguntaDiagnostico.codigo == dados.codigo.strip(),
            )
            .first()
        )
        if existente:
            raise HTTPException(status_code=409, detail="Já existe pergunta com esse código.")

    payload = dados.model_dump(exclude={"opcoes"})
    pergunta = PerguntaDiagnostico(**payload)
    if pergunta.codigo:
        pergunta.codigo = pergunta.codigo.strip()
    db.add(pergunta)
    db.flush()

    for opcao_dados in dados.opcoes:
        db.add(OpcaoPerguntaDiagnostico(pergunta_id=pergunta.id, **opcao_dados.model_dump()))

    db.commit()
    db.refresh(pergunta)
    opcoes = (
        db.query(OpcaoPerguntaDiagnostico)
        .filter(OpcaoPerguntaDiagnostico.pergunta_id == pergunta.id)
        .order_by(OpcaoPerguntaDiagnostico.ordem)
        .all()
    )

    return PerguntaDetalheResponse(
        **PerguntaResponse.model_validate(pergunta).model_dump(),
        categoria_nome=categoria.nome,
        opcoes=[OpcaoResponse.model_validate(o) for o in opcoes],
    )


@router.get("/perguntas/{pergunta_id}", response_model=PerguntaDetalheResponse)
def obter_pergunta(pergunta_id: UUID, db: Session = Depends(get_db)):
    pergunta = _pergunta_ou_404(db, pergunta_id)
    categoria = _categoria_ou_404(db, pergunta.categoria_id)
    opcoes = (
        db.query(OpcaoPerguntaDiagnostico)
        .filter(OpcaoPerguntaDiagnostico.pergunta_id == pergunta.id)
        .order_by(OpcaoPerguntaDiagnostico.ordem)
        .all()
    )
    return PerguntaDetalheResponse(
        **PerguntaResponse.model_validate(pergunta).model_dump(),
        categoria_nome=categoria.nome,
        opcoes=[OpcaoResponse.model_validate(o) for o in opcoes],
    )


@router.put("/perguntas/{pergunta_id}", response_model=PerguntaDetalheResponse)
def atualizar_pergunta(
    pergunta_id: UUID,
    dados: PerguntaUpdate,
    db: Session = Depends(get_db),
):
    pergunta = _pergunta_ou_404(db, pergunta_id)
    alteracoes = dados.model_dump(exclude_unset=True)

    if "categoria_id" in alteracoes and alteracoes["categoria_id"] is not None:
        _categoria_ou_404(db, alteracoes["categoria_id"])

    for campo, valor in alteracoes.items():
        if campo == "codigo" and valor is not None:
            valor = valor.strip()
        setattr(pergunta, campo, valor)

    db.commit()
    db.refresh(pergunta)
    return obter_pergunta(pergunta.id, db)


@router.delete("/perguntas/{pergunta_id}", response_model=PerguntaResponse)
def desativar_pergunta(pergunta_id: UUID, db: Session = Depends(get_db)):
    pergunta = _pergunta_ou_404(db, pergunta_id)
    pergunta.ativo = False
    db.commit()
    db.refresh(pergunta)
    return pergunta


@router.get("/perguntas/{pergunta_id}/opcoes", response_model=list[OpcaoResponse])
def listar_opcoes(pergunta_id: UUID, db: Session = Depends(get_db)):
    _pergunta_ou_404(db, pergunta_id)
    return (
        db.query(OpcaoPerguntaDiagnostico)
        .filter(OpcaoPerguntaDiagnostico.pergunta_id == pergunta_id)
        .order_by(OpcaoPerguntaDiagnostico.ordem, OpcaoPerguntaDiagnostico.rotulo)
        .all()
    )


@router.post(
    "/perguntas/{pergunta_id}/opcoes",
    response_model=OpcaoResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_opcao(
    pergunta_id: UUID,
    dados: OpcaoCreate,
    db: Session = Depends(get_db),
):
    _pergunta_ou_404(db, pergunta_id)
    existente = (
        db.query(OpcaoPerguntaDiagnostico)
        .filter(
            OpcaoPerguntaDiagnostico.pergunta_id == pergunta_id,
            OpcaoPerguntaDiagnostico.valor == dados.valor,
        )
        .first()
    )
    if existente:
        raise HTTPException(status_code=409, detail="Já existe opção com esse valor.")

    opcao = OpcaoPerguntaDiagnostico(pergunta_id=pergunta_id, **dados.model_dump())
    db.add(opcao)
    db.commit()
    db.refresh(opcao)
    return opcao


@router.put("/opcoes/{opcao_id}", response_model=OpcaoResponse)
def atualizar_opcao(
    opcao_id: UUID,
    dados: OpcaoUpdate,
    db: Session = Depends(get_db),
):
    opcao = _opcao_ou_404(db, opcao_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(opcao, campo, valor)
    db.commit()
    db.refresh(opcao)
    return opcao


@router.delete("/opcoes/{opcao_id}", response_model=OpcaoResponse)
def desativar_opcao(opcao_id: UUID, db: Session = Depends(get_db)):
    opcao = _opcao_ou_404(db, opcao_id)
    opcao.ativo = False
    db.commit()
    db.refresh(opcao)
    return opcao
