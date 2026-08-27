from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.security.dependencies import get_current_context
from app.models.diagnostico import (
    CategoriaDiagnostico,
    Diagnostico,
    FormularioDiagnostico,
    FormularioPergunta,
    PerguntaDiagnostico,
    RegraExibicaoPergunta,
)
from app.schemas.diagnostico import (
    FormularioCloneRequest,
    FormularioCreate,
    FormularioDetalheResponse,
    FormularioNovaVersaoRequest,
    FormularioPerguntaCreate,
    FormularioPerguntaResponse,
    FormularioPerguntaUpdate,
    FormularioResponse,
    FormularioUpdate,
    OrdenacaoFormulariosRequest,
    RegraExibicaoResponse,
)

router = APIRouter(
    prefix="/api/diagnostico/formularios",
    tags=["Diagnóstico - Formulários"],
    dependencies=[Depends(get_current_context)],
)


def _formulario_ou_404(db: Session, formulario_id: UUID) -> FormularioDiagnostico:
    formulario = db.query(FormularioDiagnostico).filter(FormularioDiagnostico.id == formulario_id).first()
    if not formulario:
        raise HTTPException(status_code=404, detail="Formulário não encontrado.")
    return formulario


def _formulario_utilizado(db: Session, formulario_id: UUID) -> bool:
    return db.query(Diagnostico.id).filter(Diagnostico.formulario_id == formulario_id).first() is not None


def _validar_formulario_estrutura_editavel(db: Session, formulario_id: UUID):
    if _formulario_utilizado(db, formulario_id):
        raise HTTPException(
            status_code=409,
            detail="Este formulário já foi utilizado em diagnóstico e sua estrutura está congelada. Crie uma nova versão.",
        )


def _pergunta_ou_404(db: Session, pergunta_id: UUID) -> PerguntaDiagnostico:
    pergunta = db.query(PerguntaDiagnostico).filter(PerguntaDiagnostico.id == pergunta_id).first()
    if not pergunta:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada.")
    return pergunta


def _associacao_ou_404(db: Session, formulario_id: UUID, pergunta_id: UUID) -> FormularioPergunta:
    associacao = db.query(FormularioPergunta).filter(
        FormularioPergunta.formulario_id == formulario_id,
        FormularioPergunta.pergunta_id == pergunta_id,
    ).first()
    if not associacao:
        raise HTTPException(status_code=404, detail="Pergunta não está associada ao formulário.")
    return associacao


def _listar_perguntas_formulario(db: Session, formulario_id: UUID) -> list[FormularioPerguntaResponse]:
    linhas = (
        db.query(FormularioPergunta, PerguntaDiagnostico, CategoriaDiagnostico)
        .join(PerguntaDiagnostico, PerguntaDiagnostico.id == FormularioPergunta.pergunta_id)
        .join(CategoriaDiagnostico, CategoriaDiagnostico.id == PerguntaDiagnostico.categoria_id)
        .filter(FormularioPergunta.formulario_id == formulario_id)
        .order_by(FormularioPergunta.ordem, PerguntaDiagnostico.codigo)
        .all()
    )
    return [
        FormularioPerguntaResponse(
            id=fp.id,
            formulario_id=fp.formulario_id,
            pergunta_id=p.id,
            ordem=fp.ordem,
            obrigatoria=fp.obrigatoria,
            peso=fp.peso,
            ativo=fp.ativo,
            codigo=p.codigo,
            pergunta=p.pergunta,
            categoria_id=c.id,
            categoria_nome=c.nome,
            tipo_resposta=p.tipo_resposta,
            natureza=p.natureza,
        )
        for fp, p, c in linhas
    ]


def _listar_regras_formulario(db: Session, formulario_id: UUID) -> list[RegraExibicaoResponse]:
    regras = db.query(RegraExibicaoPergunta).filter(
        RegraExibicaoPergunta.formulario_id == formulario_id
    ).order_by(RegraExibicaoPergunta.created_at, RegraExibicaoPergunta.id).all()
    return [RegraExibicaoResponse.model_validate(r) for r in regras]


@router.get("", response_model=list[FormularioResponse])
def listar_formularios(
    ativo: bool | None = None,
    tipo: str | None = None,
    empresa_id: UUID | None = None,
    incluir_globais: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(FormularioDiagnostico)
    if ativo is not None:
        query = query.filter(FormularioDiagnostico.ativo == ativo)
    if tipo:
        query = query.filter(FormularioDiagnostico.tipo == tipo)
    if empresa_id is not None:
        if incluir_globais:
            query = query.filter(or_(FormularioDiagnostico.empresa_id == empresa_id, FormularioDiagnostico.empresa_id.is_(None)))
        else:
            query = query.filter(FormularioDiagnostico.empresa_id == empresa_id)
    elif not incluir_globais:
        query = query.filter(FormularioDiagnostico.empresa_id.is_not(None))
    formularios = query.order_by(FormularioDiagnostico.nome, FormularioDiagnostico.versao).all()
    return [
        FormularioResponse(
            **FormularioResponse.model_validate(f).model_dump(exclude={"utilizado_em_diagnostico"}),
            utilizado_em_diagnostico=_formulario_utilizado(db, f.id),
        )
        for f in formularios
    ]


@router.post("", response_model=FormularioResponse, status_code=status.HTTP_201_CREATED)
def criar_formulario(dados: FormularioCreate, db: Session = Depends(get_db)):
    payload = dados.model_dump()
    payload["versao"] = 1
    empresa_filter = FormularioDiagnostico.empresa_id.is_(None) if dados.empresa_id is None else FormularioDiagnostico.empresa_id == dados.empresa_id
    existente = db.query(FormularioDiagnostico).filter(
        empresa_filter,
        FormularioDiagnostico.codigo == dados.codigo.strip(),
        FormularioDiagnostico.versao == 1,
    ).first()
    if existente:
        raise HTTPException(status_code=409, detail="Já existe formulário com esse código e versão.")
    formulario = FormularioDiagnostico(**payload)
    formulario.codigo = formulario.codigo.strip()
    formulario.nome = formulario.nome.strip()
    db.add(formulario)
    db.commit()
    db.refresh(formulario)
    return formulario


@router.post("/{formulario_id}/clonar", response_model=FormularioDetalheResponse, status_code=status.HTTP_201_CREATED)
def clonar_formulario(formulario_id: UUID, dados: FormularioCloneRequest, db: Session = Depends(get_db)):
    """
    Clona a estrutura de um formulário:
    - cria novo registro em formularios_diagnostico;
    - cria novas associações em formularios_perguntas;
    - cria novas regras em regras_exibicao_perguntas.

    Perguntas e opções do catálogo NÃO são duplicadas: o clone referencia
    os mesmos pergunta_id/opcao_origem_id, preservando o catálogo reutilizável.
    """
    origem = _formulario_ou_404(db, formulario_id)

    empresa_destino = dados.empresa_id
    empresa_filter = (
        FormularioDiagnostico.empresa_id.is_(None)
        if empresa_destino is None
        else FormularioDiagnostico.empresa_id == empresa_destino
    )
    existente = db.query(FormularioDiagnostico).filter(
        empresa_filter,
        FormularioDiagnostico.codigo == dados.codigo.strip(),
        FormularioDiagnostico.versao == dados.versao,
    ).first()
    if existente:
        raise HTTPException(status_code=409, detail="Já existe formulário com esse código e versão.")

    novo = FormularioDiagnostico(
        empresa_id=empresa_destino,
        codigo=dados.codigo.strip(),
        nome=dados.nome.strip(),
        descricao=dados.descricao if dados.descricao is not None else origem.descricao,
        tipo=dados.tipo.strip(),
        versao=dados.versao,
        ativo=dados.ativo,
    )
    db.add(novo)
    db.flush()

    associacoes = (
        db.query(FormularioPergunta)
        .filter(FormularioPergunta.formulario_id == origem.id)
        .order_by(FormularioPergunta.ordem, FormularioPergunta.id)
        .all()
    )
    for fp in associacoes:
        db.add(FormularioPergunta(
            formulario_id=novo.id,
            pergunta_id=fp.pergunta_id,
            ordem=fp.ordem,
            obrigatoria=fp.obrigatoria,
            peso=fp.peso,  # campo legado: copiado apenas por compatibilidade estrutural
            ativo=fp.ativo,
        ))

    regras = (
        db.query(RegraExibicaoPergunta)
        .filter(RegraExibicaoPergunta.formulario_id == origem.id)
        .order_by(RegraExibicaoPergunta.created_at, RegraExibicaoPergunta.id)
        .all()
    )
    for regra in regras:
        db.add(RegraExibicaoPergunta(
            formulario_id=novo.id,
            pergunta_origem_id=regra.pergunta_origem_id,
            opcao_origem_id=regra.opcao_origem_id,
            pergunta_destino_id=regra.pergunta_destino_id,
        ))

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(novo)
    return FormularioDetalheResponse(
        **FormularioResponse.model_validate(novo).model_dump(),
        perguntas=_listar_perguntas_formulario(db, novo.id),
        regras_exibicao=_listar_regras_formulario(db, novo.id),
    )


@router.post("/{formulario_id}/nova-versao", response_model=FormularioDetalheResponse, status_code=status.HTTP_201_CREATED)
def criar_nova_versao(formulario_id: UUID, dados: FormularioNovaVersaoRequest, db: Session = Depends(get_db)):
    origem = _formulario_ou_404(db, formulario_id)
    empresa_filter = FormularioDiagnostico.empresa_id.is_(None) if origem.empresa_id is None else FormularioDiagnostico.empresa_id == origem.empresa_id

    maior = (
        db.query(FormularioDiagnostico.versao)
        .filter(empresa_filter, FormularioDiagnostico.codigo == origem.codigo)
        .order_by(FormularioDiagnostico.versao.desc())
        .first()
    )
    proxima = int(maior[0]) + 1 if maior else 1

    novo = FormularioDiagnostico(
        empresa_id=origem.empresa_id,
        codigo=origem.codigo,
        nome=(dados.nome or origem.nome).strip(),
        descricao=dados.descricao if dados.descricao is not None else origem.descricao,
        tipo=origem.tipo,
        versao=proxima,
        ativo=dados.ativo,
    )
    db.add(novo)
    db.flush()

    for fp in db.query(FormularioPergunta).filter(FormularioPergunta.formulario_id == origem.id).all():
        db.add(FormularioPergunta(
            formulario_id=novo.id, pergunta_id=fp.pergunta_id, ordem=fp.ordem,
            obrigatoria=fp.obrigatoria, peso=fp.peso, ativo=fp.ativo
        ))

    for regra in db.query(RegraExibicaoPergunta).filter(RegraExibicaoPergunta.formulario_id == origem.id).all():
        db.add(RegraExibicaoPergunta(
            formulario_id=novo.id,
            pergunta_origem_id=regra.pergunta_origem_id,
            opcao_origem_id=regra.opcao_origem_id,
            pergunta_destino_id=regra.pergunta_destino_id,
        ))

    db.commit()
    db.refresh(novo)
    return FormularioDetalheResponse(
        **FormularioResponse.model_validate(novo).model_dump(exclude={"utilizado_em_diagnostico"}),
        utilizado_em_diagnostico=False,
        perguntas=_listar_perguntas_formulario(db, novo.id),
        regras_exibicao=_listar_regras_formulario(db, novo.id),
    )


@router.get("/{formulario_id}", response_model=FormularioDetalheResponse)
def obter_formulario(formulario_id: UUID, db: Session = Depends(get_db)):
    formulario = _formulario_ou_404(db, formulario_id)
    return FormularioDetalheResponse(
        **FormularioResponse.model_validate(formulario).model_dump(exclude={"utilizado_em_diagnostico"}),
        utilizado_em_diagnostico=_formulario_utilizado(db, formulario.id),
        perguntas=_listar_perguntas_formulario(db, formulario.id),
        regras_exibicao=_listar_regras_formulario(db, formulario.id),
    )


@router.put("/{formulario_id}", response_model=FormularioResponse)
def atualizar_formulario(formulario_id: UUID, dados: FormularioUpdate, db: Session = Depends(get_db)):
    formulario = _formulario_ou_404(db, formulario_id)
    alteracoes = dados.model_dump(exclude_unset=True)

    if "versao" in alteracoes and alteracoes["versao"] is not None and int(alteracoes["versao"]) != int(formulario.versao):
        raise HTTPException(status_code=409, detail="A versão é controlada pelo sistema. Use Nova versão.")
    if "codigo" in alteracoes and alteracoes["codigo"] is not None and alteracoes["codigo"].strip() != formulario.codigo:
        raise HTTPException(status_code=409, detail="O código não pode ser alterado. Use Clonar para criar outro formulário.")

    alteracoes.pop("versao", None)
    alteracoes.pop("codigo", None)
    for campo, valor in alteracoes.items():
        if campo == "nome" and valor is not None:
            valor = valor.strip()
        setattr(formulario, campo, valor)
    db.commit()
    db.refresh(formulario)
    return formulario


@router.delete("/{formulario_id}", response_model=FormularioResponse)
def desativar_formulario(formulario_id: UUID, db: Session = Depends(get_db)):
    formulario = _formulario_ou_404(db, formulario_id)
    formulario.ativo = False
    db.commit()
    db.refresh(formulario)
    return formulario


@router.get("/{formulario_id}/perguntas", response_model=list[FormularioPerguntaResponse])
def listar_perguntas_formulario(formulario_id: UUID, db: Session = Depends(get_db)):
    _formulario_ou_404(db, formulario_id)
    return _listar_perguntas_formulario(db, formulario_id)


@router.post("/{formulario_id}/perguntas", response_model=FormularioPerguntaResponse, status_code=status.HTTP_201_CREATED)
def adicionar_pergunta_formulario(formulario_id: UUID, dados: FormularioPerguntaCreate, db: Session = Depends(get_db)):
    _formulario_ou_404(db, formulario_id)
    _validar_formulario_estrutura_editavel(db, formulario_id)
    pergunta = _pergunta_ou_404(db, dados.pergunta_id)
    existente = db.query(FormularioPergunta).filter(
        FormularioPergunta.formulario_id == formulario_id,
        FormularioPergunta.pergunta_id == dados.pergunta_id,
    ).first()
    if existente:
        raise HTTPException(status_code=409, detail="Pergunta já está neste formulário.")
    associacao = FormularioPergunta(formulario_id=formulario_id, **dados.model_dump())
    db.add(associacao)
    db.commit()
    db.refresh(associacao)
    categoria = db.query(CategoriaDiagnostico).filter(CategoriaDiagnostico.id == pergunta.categoria_id).first()
    return FormularioPerguntaResponse(
        id=associacao.id,
        formulario_id=associacao.formulario_id,
        pergunta_id=pergunta.id,
        ordem=associacao.ordem,
        obrigatoria=associacao.obrigatoria,
        peso=associacao.peso,
        ativo=associacao.ativo,
        codigo=pergunta.codigo,
        pergunta=pergunta.pergunta,
        categoria_id=pergunta.categoria_id,
        categoria_nome=categoria.nome,
        tipo_resposta=pergunta.tipo_resposta,
        natureza=pergunta.natureza,
    )


@router.delete("/{formulario_id}/perguntas/{pergunta_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_pergunta_formulario(formulario_id: UUID, pergunta_id: UUID, db: Session = Depends(get_db)):
    _formulario_ou_404(db, formulario_id)
    _validar_formulario_estrutura_editavel(db, formulario_id)
    associacao = _associacao_ou_404(db, formulario_id, pergunta_id)
    # Regras dependentes são removidas pelas FKs apenas quando a pergunta/formulário é
    # apagado. Ao remover a associação, removemos explicitamente regras relacionadas.
    db.query(RegraExibicaoPergunta).filter(
        RegraExibicaoPergunta.formulario_id == formulario_id,
        or_(
            RegraExibicaoPergunta.pergunta_origem_id == pergunta_id,
            RegraExibicaoPergunta.pergunta_destino_id == pergunta_id,
        ),
    ).delete(synchronize_session=False)
    db.delete(associacao)
    db.commit()
    return None


@router.put("/{formulario_id}/perguntas/ordenacao", response_model=list[FormularioPerguntaResponse])
def reordenar_perguntas_formulario(formulario_id: UUID, dados: OrdenacaoFormulariosRequest, db: Session = Depends(get_db)):
    _formulario_ou_404(db, formulario_id)
    _validar_formulario_estrutura_editavel(db, formulario_id)
    ids_recebidos = [item.pergunta_id for item in dados.itens]
    if len(ids_recebidos) != len(set(ids_recebidos)):
        raise HTTPException(status_code=400, detail="A lista de ordenação contém perguntas duplicadas.")
    associacoes = db.query(FormularioPergunta).filter(
        FormularioPergunta.formulario_id == formulario_id,
        FormularioPergunta.pergunta_id.in_(ids_recebidos),
    ).all()
    por_pergunta = {item.pergunta_id: item for item in associacoes}
    faltantes = [str(pid) for pid in ids_recebidos if pid not in por_pergunta]
    if faltantes:
        raise HTTPException(status_code=400, detail={"mensagem": "Uma ou mais perguntas não pertencem ao formulário.", "perguntas": faltantes})
    for item in dados.itens:
        por_pergunta[item.pergunta_id].ordem = item.ordem
    db.commit()
    return _listar_perguntas_formulario(db, formulario_id)


@router.put("/{formulario_id}/perguntas/{pergunta_id}", response_model=FormularioPerguntaResponse)
def atualizar_pergunta_formulario(formulario_id: UUID, pergunta_id: UUID, dados: FormularioPerguntaUpdate, db: Session = Depends(get_db)):
    _formulario_ou_404(db, formulario_id)
    _validar_formulario_estrutura_editavel(db, formulario_id)
    associacao = _associacao_ou_404(db, formulario_id, pergunta_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(associacao, campo, valor)
    db.commit()
    return next(item for item in _listar_perguntas_formulario(db, formulario_id) if item.pergunta_id == pergunta_id)
