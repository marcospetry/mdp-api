from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.orm import Session

from app.database import get_db
from app.security.dependencies import get_current_context
from app.models.diagnostico import (
    CategoriaDiagnostico,
    FaixaAvaliacaoNumero,
    OpcaoPerguntaDiagnostico,
    PerguntaDiagnostico,
    RespostaDiagnostico,
)
from app.schemas.diagnostico import (
    CategoriaCreate,
    CategoriaResponse,
    CategoriaUpdate,
    FaixaResponse,
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


def _rollback_http(db: Session, exc: Exception):
    db.rollback()
    if isinstance(exc, IntegrityError):
        raise HTTPException(status_code=409, detail="Conflito com uma regra de integridade do diagnóstico.")
    if isinstance(exc, DBAPIError):
        mensagem = str(getattr(exc, "orig", exc))
        if "Pergunta CONTEXTO" in mensagem:
            raise HTTPException(status_code=400, detail="Pergunta CONTEXTO não aceita estado interno.")
        if "não utiliza opcoes_pergunta_diagnostico" in mensagem:
            raise HTTPException(status_code=400, detail="Este tipo de pergunta não utiliza opções.")
        raise HTTPException(status_code=400, detail="Dados incompatíveis com as regras do diagnóstico.")
    raise exc


def _validar_opcao_para_pergunta(pergunta: PerguntaDiagnostico, estado_interno: str | None):
    if pergunta.tipo_resposta in {"NUMERO", "TEXTO_CURTO"}:
        raise HTTPException(status_code=400, detail=f"Pergunta {pergunta.tipo_resposta} não utiliza opções.")
    if pergunta.natureza == "CONTEXTO" and estado_interno is not None:
        raise HTTPException(status_code=400, detail="Pergunta CONTEXTO não aceita estado_interno.")
    if pergunta.natureza == "AVALIATIVA" and pergunta.tipo_resposta == "ESCOLHA_UNICA" and estado_interno is None:
        raise HTTPException(status_code=400, detail="Opção de pergunta AVALIATIVA exige estado_interno.")


def _detalhe_pergunta(db: Session, pergunta: PerguntaDiagnostico) -> PerguntaDetalheResponse:
    categoria = _categoria_ou_404(db, pergunta.categoria_id)
    opcoes = (
        db.query(OpcaoPerguntaDiagnostico)
        .filter(OpcaoPerguntaDiagnostico.pergunta_id == pergunta.id)
        .order_by(OpcaoPerguntaDiagnostico.ordem, OpcaoPerguntaDiagnostico.rotulo)
        .all()
    )
    faixas = (
        db.query(FaixaAvaliacaoNumero)
        .filter(FaixaAvaliacaoNumero.pergunta_id == pergunta.id)
        .order_by(FaixaAvaliacaoNumero.valor_min.asc().nullsfirst())
        .all()
    )
    return PerguntaDetalheResponse(
        **PerguntaResponse.model_validate(pergunta).model_dump(),
        categoria_nome=categoria.nome,
        opcoes=[OpcaoResponse.model_validate(o) for o in opcoes],
        faixas=[FaixaResponse.model_validate(f) for f in faixas],
        utilizada_em_resposta=_pergunta_utilizada_em_resposta(db, pergunta.id),
    )


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
            query = query.filter(or_(CategoriaDiagnostico.empresa_id == empresa_id, CategoriaDiagnostico.empresa_id.is_(None)))
        else:
            query = query.filter(CategoriaDiagnostico.empresa_id == empresa_id)
    elif not incluir_globais:
        query = query.filter(CategoriaDiagnostico.empresa_id.is_not(None))
    if ativo is not None:
        query = query.filter(CategoriaDiagnostico.ativo == ativo)
    return query.order_by(CategoriaDiagnostico.ordem, CategoriaDiagnostico.nome).all()


def _categoria_mesmo_escopo_query(db: Session, empresa_id: UUID | None):
    query = db.query(CategoriaDiagnostico)
    if empresa_id is None:
        return query.filter(CategoriaDiagnostico.empresa_id.is_(None))
    return query.filter(CategoriaDiagnostico.empresa_id == empresa_id)


def _ordens_ativas_categoria(db: Session, empresa_id: UUID | None, ignorar_id: UUID | None = None) -> set[int]:
    query = _categoria_mesmo_escopo_query(db, empresa_id).filter(CategoriaDiagnostico.ativo.is_(True))
    if ignorar_id is not None:
        query = query.filter(CategoriaDiagnostico.id != ignorar_id)
    return {int(c.ordem) for c in query.all() if c.ordem is not None and int(c.ordem) > 0}


def _proxima_ordem_categoria(db: Session, empresa_id: UUID | None, ignorar_id: UUID | None = None) -> int:
    usadas = _ordens_ativas_categoria(db, empresa_id, ignorar_id)
    ordem = 1
    while ordem in usadas:
        ordem += 1
    return ordem


def _pergunta_utilizada_em_resposta(db: Session, pergunta_id: UUID) -> bool:
    return db.query(RespostaDiagnostico.id).filter(RespostaDiagnostico.pergunta_id == pergunta_id).first() is not None


def _validar_pergunta_editavel(db: Session, pergunta_id: UUID):
    if _pergunta_utilizada_em_resposta(db, pergunta_id):
        raise HTTPException(
            status_code=409,
            detail="Esta pergunta já possui respostas em diagnósticos e está congelada. Crie uma nova pergunta para alterar seu significado.",
        )


@router.post("/categorias", response_model=CategoriaResponse, status_code=status.HTTP_201_CREATED)
def criar_categoria(dados: CategoriaCreate, db: Session = Depends(get_db)):
    existente = (
        db.query(CategoriaDiagnostico)
        .filter(
            CategoriaDiagnostico.empresa_id.is_(None) if dados.empresa_id is None else CategoriaDiagnostico.empresa_id == dados.empresa_id,
            CategoriaDiagnostico.nome.ilike(dados.nome.strip()),
        )
        .first()
    )
    if existente:
        raise HTTPException(status_code=409, detail="Já existe categoria com esse nome.")
    payload = dados.model_dump()
    payload["ordem"] = _proxima_ordem_categoria(db, dados.empresa_id)
    categoria = CategoriaDiagnostico(**payload)
    categoria.nome = categoria.nome.strip()
    db.add(categoria)
    try:
        db.commit()
    except (IntegrityError, DBAPIError) as exc:
        _rollback_http(db, exc)
    db.refresh(categoria)
    return categoria


@router.get("/categorias/{categoria_id}", response_model=CategoriaResponse)
def obter_categoria(categoria_id: UUID, db: Session = Depends(get_db)):
    return _categoria_ou_404(db, categoria_id)


@router.put("/categorias/{categoria_id}", response_model=CategoriaResponse)
def atualizar_categoria(categoria_id: UUID, dados: CategoriaUpdate, db: Session = Depends(get_db)):
    categoria = _categoria_ou_404(db, categoria_id)
    alteracoes = dados.model_dump(exclude_unset=True)

    if "ordem" in alteracoes and alteracoes["ordem"] is not None and int(alteracoes["ordem"]) != int(categoria.ordem):
        raise HTTPException(status_code=409, detail="A ordem da categoria é controlada automaticamente.")

    if alteracoes.get("ativo") is True and not categoria.ativo:
        usadas = _ordens_ativas_categoria(db, categoria.empresa_id, ignorar_id=categoria.id)
        if int(categoria.ordem) in usadas:
            categoria.ordem = _proxima_ordem_categoria(db, categoria.empresa_id, ignorar_id=categoria.id)

    alteracoes.pop("ordem", None)

    for campo, valor in alteracoes.items():
        if campo == "nome" and valor is not None:
            valor = valor.strip()
        setattr(categoria, campo, valor)
    try:
        db.commit()
    except (IntegrityError, DBAPIError) as exc:
        _rollback_http(db, exc)
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
    natureza: str | None = None,
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
    if natureza:
        query = query.filter(PerguntaDiagnostico.natureza == natureza)
    if busca:
        termo = f"%{busca.strip()}%"
        query = query.filter(or_(PerguntaDiagnostico.codigo.ilike(termo), PerguntaDiagnostico.pergunta.ilike(termo)))
    if empresa_id is not None:
        if incluir_globais:
            query = query.filter(or_(PerguntaDiagnostico.empresa_id == empresa_id, PerguntaDiagnostico.empresa_id.is_(None)))
        else:
            query = query.filter(PerguntaDiagnostico.empresa_id == empresa_id)
    elif not incluir_globais:
        query = query.filter(PerguntaDiagnostico.empresa_id.is_not(None))
    return query.order_by(PerguntaDiagnostico.ordem, PerguntaDiagnostico.codigo).all()


@router.post("/perguntas", response_model=PerguntaDetalheResponse, status_code=status.HTTP_201_CREATED)
def criar_pergunta(dados: PerguntaCreate, db: Session = Depends(get_db)):
    _categoria_ou_404(db, dados.categoria_id)
    if dados.codigo:
        existente = (
            db.query(PerguntaDiagnostico)
            .filter(
                PerguntaDiagnostico.empresa_id.is_(None) if dados.empresa_id is None else PerguntaDiagnostico.empresa_id == dados.empresa_id,
                PerguntaDiagnostico.codigo == dados.codigo.strip(),
            )
            .first()
        )
        if existente:
            raise HTTPException(status_code=409, detail="Já existe pergunta com esse código.")

    payload = dados.model_dump(exclude={"opcoes", "faixas"})
    pergunta = PerguntaDiagnostico(**payload)
    if pergunta.codigo:
        pergunta.codigo = pergunta.codigo.strip()
    db.add(pergunta)
    db.flush()

    for opcao_dados in dados.opcoes:
        _validar_opcao_para_pergunta(pergunta, opcao_dados.estado_interno)
        db.add(OpcaoPerguntaDiagnostico(pergunta_id=pergunta.id, **opcao_dados.model_dump()))

    for faixa_dados in dados.faixas:
        if pergunta.tipo_resposta != "NUMERO" or pergunta.natureza != "AVALIATIVA":
            raise HTTPException(status_code=400, detail="Faixas exigem pergunta NUMERO AVALIATIVA.")
        db.add(FaixaAvaliacaoNumero(pergunta_id=pergunta.id, **faixa_dados.model_dump()))

    try:
        db.commit()
    except (IntegrityError, DBAPIError) as exc:
        _rollback_http(db, exc)
    db.refresh(pergunta)
    return _detalhe_pergunta(db, pergunta)


@router.get("/perguntas/{pergunta_id}", response_model=PerguntaDetalheResponse)
def obter_pergunta(pergunta_id: UUID, db: Session = Depends(get_db)):
    return _detalhe_pergunta(db, _pergunta_ou_404(db, pergunta_id))


@router.put("/perguntas/{pergunta_id}", response_model=PerguntaDetalheResponse)
def atualizar_pergunta(pergunta_id: UUID, dados: PerguntaUpdate, db: Session = Depends(get_db)):
    pergunta = _pergunta_ou_404(db, pergunta_id)
    _validar_pergunta_editavel(db, pergunta_id)
    alteracoes = dados.model_dump(exclude_unset=True)
    if "categoria_id" in alteracoes and alteracoes["categoria_id"] is not None:
        _categoria_ou_404(db, alteracoes["categoria_id"])

    tipo_final = alteracoes.get("tipo_resposta", pergunta.tipo_resposta)
    natureza_final = alteracoes.get("natureza", pergunta.natureza)
    ideal_final = alteracoes.get("ideal", pergunta.ideal)
    sugestao_final = alteracoes.get("sugestao", pergunta.sugestao)

    if tipo_final in {"MULTIPLA_ESCOLHA", "TEXTO_CURTO"} and natureza_final != "CONTEXTO":
        raise HTTPException(status_code=400, detail=f"{tipo_final} deve usar natureza CONTEXTO.")
    if natureza_final == "AVALIATIVA" and (not ideal_final or not str(ideal_final).strip() or not sugestao_final or not str(sugestao_final).strip()):
        raise HTTPException(status_code=400, detail="Pergunta AVALIATIVA exige ideal e sugestao.")

    opcoes_existentes = db.query(OpcaoPerguntaDiagnostico).filter(OpcaoPerguntaDiagnostico.pergunta_id == pergunta_id).count()
    faixas_existentes = db.query(FaixaAvaliacaoNumero).filter(FaixaAvaliacaoNumero.pergunta_id == pergunta_id).count()
    estados_em_opcoes = db.query(OpcaoPerguntaDiagnostico).filter(
        OpcaoPerguntaDiagnostico.pergunta_id == pergunta_id,
        OpcaoPerguntaDiagnostico.estado_interno.is_not(None),
    ).count()

    if tipo_final in {"NUMERO", "TEXTO_CURTO"} and opcoes_existentes:
        raise HTTPException(status_code=409, detail="Remova/desative as opções antes de alterar para este tipo de resposta.")
    if tipo_final != "NUMERO" and faixas_existentes:
        raise HTTPException(status_code=409, detail="Remova as faixas antes de alterar o tipo da pergunta.")
    if natureza_final == "CONTEXTO" and (estados_em_opcoes or faixas_existentes):
        raise HTTPException(status_code=409, detail="Remova estados/faixas de avaliação antes de alterar a pergunta para CONTEXTO.")

    for campo, valor in alteracoes.items():
        if campo == "codigo" and valor is not None:
            valor = valor.strip()
        setattr(pergunta, campo, valor)
    try:
        db.commit()
    except (IntegrityError, DBAPIError) as exc:
        _rollback_http(db, exc)
    db.refresh(pergunta)
    return _detalhe_pergunta(db, pergunta)


@router.delete("/perguntas/{pergunta_id}", response_model=PerguntaResponse)
def desativar_pergunta(pergunta_id: UUID, db: Session = Depends(get_db)):
    pergunta = _pergunta_ou_404(db, pergunta_id)
    _validar_pergunta_editavel(db, pergunta_id)
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


@router.post("/perguntas/{pergunta_id}/opcoes", response_model=OpcaoResponse, status_code=status.HTTP_201_CREATED)
def criar_opcao(pergunta_id: UUID, dados: OpcaoCreate, db: Session = Depends(get_db)):
    pergunta = _pergunta_ou_404(db, pergunta_id)
    _validar_pergunta_editavel(db, pergunta_id)
    _validar_opcao_para_pergunta(pergunta, dados.estado_interno)
    existente = db.query(OpcaoPerguntaDiagnostico).filter(
        OpcaoPerguntaDiagnostico.pergunta_id == pergunta_id,
        OpcaoPerguntaDiagnostico.valor == dados.valor,
    ).first()
    if existente:
        raise HTTPException(status_code=409, detail="Já existe opção com esse valor.")
    opcao = OpcaoPerguntaDiagnostico(pergunta_id=pergunta_id, **dados.model_dump())
    db.add(opcao)
    try:
        db.commit()
    except (IntegrityError, DBAPIError) as exc:
        _rollback_http(db, exc)
    db.refresh(opcao)
    return opcao


@router.put("/opcoes/{opcao_id}", response_model=OpcaoResponse)
def atualizar_opcao(opcao_id: UUID, dados: OpcaoUpdate, db: Session = Depends(get_db)):
    opcao = _opcao_ou_404(db, opcao_id)
    pergunta = _pergunta_ou_404(db, opcao.pergunta_id)
    _validar_pergunta_editavel(db, pergunta.id)
    alteracoes = dados.model_dump(exclude_unset=True)
    estado_final = alteracoes.get("estado_interno", opcao.estado_interno)
    _validar_opcao_para_pergunta(pergunta, estado_final)
    for campo, valor in alteracoes.items():
        setattr(opcao, campo, valor)
    try:
        db.commit()
    except (IntegrityError, DBAPIError) as exc:
        _rollback_http(db, exc)
    db.refresh(opcao)
    return opcao


@router.delete("/opcoes/{opcao_id}", response_model=OpcaoResponse)
def desativar_opcao(opcao_id: UUID, db: Session = Depends(get_db)):
    opcao = _opcao_ou_404(db, opcao_id)
    _validar_pergunta_editavel(db, opcao.pergunta_id)
    opcao.ativo = False
    db.commit()
    db.refresh(opcao)
    return opcao
