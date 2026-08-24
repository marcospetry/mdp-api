from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.diagnostico import (
    FaixaAvaliacaoNumero,
    FormularioDiagnostico,
    FormularioPergunta,
    OpcaoPerguntaDiagnostico,
    PerguntaDiagnostico,
    RegraExibicaoPergunta,
)
from app.schemas.diagnostico import (
    FaixaCreate,
    FaixaResponse,
    FaixaUpdate,
    MetadadosDiagnosticoResponse,
    RegraExibicaoCreate,
    RegraExibicaoResponse,
    RegraExibicaoUpdate,
)
from app.security.dependencies import get_current_context

router = APIRouter(
    prefix="/api/diagnostico",
    tags=["Diagnóstico - Estrutura"],
    dependencies=[Depends(get_current_context)],
)

TIPOS_RESPOSTA = ["ESCOLHA_UNICA", "MULTIPLA_ESCOLHA", "NUMERO", "TEXTO_CURTO"]
NATUREZAS = ["AVALIATIVA", "CONTEXTO"]
ESTADOS_INTERNOS = ["ALTO", "MEDIO", "BAIXO", "NA", "NAO_SEI"]


def _pergunta_ou_404(db: Session, pergunta_id: UUID):
    obj = db.query(PerguntaDiagnostico).filter(PerguntaDiagnostico.id == pergunta_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada.")
    return obj


def _formulario_ou_404(db: Session, formulario_id: UUID):
    obj = db.query(FormularioDiagnostico).filter(FormularioDiagnostico.id == formulario_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Formulário não encontrado.")
    return obj


def _faixa_ou_404(db: Session, faixa_id: UUID):
    obj = db.query(FaixaAvaliacaoNumero).filter(FaixaAvaliacaoNumero.id == faixa_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Faixa não encontrada.")
    return obj


def _regra_ou_404(db: Session, regra_id: UUID):
    obj = db.query(RegraExibicaoPergunta).filter(RegraExibicaoPergunta.id == regra_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Regra de exibição não encontrada.")
    return obj


def _commit(db: Session):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Conflito com uma regra de integridade do diagnóstico.")
    except DBAPIError as exc:
        db.rollback()
        msg = str(getattr(exc, "orig", exc))
        if "sobrepõe" in msg:
            raise HTTPException(status_code=409, detail="Faixa numérica sobrepõe outra faixa existente.")
        if "NUMERO AVALIATIVA" in msg:
            raise HTTPException(status_code=400, detail="Faixas são permitidas somente em pergunta NUMERO AVALIATIVA.")
        if "não pertence" in msg:
            raise HTTPException(status_code=400, detail="A opção de origem não pertence à pergunta de origem.")
        if "não está ativa no formulário" in msg:
            raise HTTPException(status_code=400, detail="Perguntas da regra devem estar ativas no formulário.")
        raise HTTPException(status_code=400, detail="Dados incompatíveis com as regras do diagnóstico.")


@router.get("/metadados", response_model=MetadadosDiagnosticoResponse)
def obter_metadados():
    return MetadadosDiagnosticoResponse(
        tipos_resposta=TIPOS_RESPOSTA,
        naturezas=NATUREZAS,
        estados_internos=ESTADOS_INTERNOS,
    )


@router.get("/perguntas/{pergunta_id}/faixas", response_model=list[FaixaResponse])
def listar_faixas(pergunta_id: UUID, db: Session = Depends(get_db)):
    _pergunta_ou_404(db, pergunta_id)
    return db.query(FaixaAvaliacaoNumero).filter(
        FaixaAvaliacaoNumero.pergunta_id == pergunta_id
    ).order_by(FaixaAvaliacaoNumero.valor_min.asc().nullsfirst()).all()


@router.post("/perguntas/{pergunta_id}/faixas", response_model=FaixaResponse, status_code=status.HTTP_201_CREATED)
def criar_faixa(pergunta_id: UUID, dados: FaixaCreate, db: Session = Depends(get_db)):
    pergunta = _pergunta_ou_404(db, pergunta_id)
    if pergunta.tipo_resposta != "NUMERO" or pergunta.natureza != "AVALIATIVA":
        raise HTTPException(status_code=400, detail="Faixas exigem pergunta NUMERO AVALIATIVA.")
    faixa = FaixaAvaliacaoNumero(pergunta_id=pergunta_id, **dados.model_dump())
    db.add(faixa)
    _commit(db)
    db.refresh(faixa)
    return faixa


@router.put("/faixas/{faixa_id}", response_model=FaixaResponse)
def atualizar_faixa(faixa_id: UUID, dados: FaixaUpdate, db: Session = Depends(get_db)):
    faixa = _faixa_ou_404(db, faixa_id)
    alteracoes = dados.model_dump(exclude_unset=True)
    valor_min = alteracoes.get("valor_min", faixa.valor_min)
    valor_max = alteracoes.get("valor_max", faixa.valor_max)
    if valor_min is not None and valor_max is not None and valor_min > valor_max:
        raise HTTPException(status_code=400, detail="valor_min deve ser menor ou igual a valor_max.")
    for campo, valor in alteracoes.items():
        setattr(faixa, campo, valor)
    _commit(db)
    db.refresh(faixa)
    return faixa


@router.delete("/faixas/{faixa_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_faixa(faixa_id: UUID, db: Session = Depends(get_db)):
    faixa = _faixa_ou_404(db, faixa_id)
    db.delete(faixa)
    _commit(db)
    return None


@router.get("/formularios/{formulario_id}/regras-exibicao", response_model=list[RegraExibicaoResponse])
def listar_regras(formulario_id: UUID, db: Session = Depends(get_db)):
    _formulario_ou_404(db, formulario_id)
    return db.query(RegraExibicaoPergunta).filter(
        RegraExibicaoPergunta.formulario_id == formulario_id
    ).order_by(RegraExibicaoPergunta.created_at, RegraExibicaoPergunta.id).all()


@router.post("/formularios/{formulario_id}/regras-exibicao", response_model=RegraExibicaoResponse, status_code=status.HTTP_201_CREATED)
def criar_regra(formulario_id: UUID, dados: RegraExibicaoCreate, db: Session = Depends(get_db)):
    _formulario_ou_404(db, formulario_id)
    if dados.pergunta_origem_id == dados.pergunta_destino_id:
        raise HTTPException(status_code=400, detail="Pergunta de origem e destino devem ser diferentes.")

    origem = _pergunta_ou_404(db, dados.pergunta_origem_id)
    _pergunta_ou_404(db, dados.pergunta_destino_id)
    opcao = db.query(OpcaoPerguntaDiagnostico).filter(OpcaoPerguntaDiagnostico.id == dados.opcao_origem_id).first()
    if not opcao or opcao.pergunta_id != origem.id:
        raise HTTPException(status_code=400, detail="A opção de origem não pertence à pergunta de origem.")

    for pid in (dados.pergunta_origem_id, dados.pergunta_destino_id):
        existe = db.query(FormularioPergunta).filter(
            FormularioPergunta.formulario_id == formulario_id,
            FormularioPergunta.pergunta_id == pid,
            FormularioPergunta.ativo.is_(True),
        ).first()
        if not existe:
            raise HTTPException(status_code=400, detail="Perguntas da regra devem estar ativas no formulário.")

    regra = RegraExibicaoPergunta(formulario_id=formulario_id, **dados.model_dump())
    db.add(regra)
    _commit(db)
    db.refresh(regra)
    return regra


@router.put("/regras-exibicao/{regra_id}", response_model=RegraExibicaoResponse)
def atualizar_regra(regra_id: UUID, dados: RegraExibicaoUpdate, db: Session = Depends(get_db)):
    regra = _regra_ou_404(db, regra_id)
    origem_id = dados.pergunta_origem_id or regra.pergunta_origem_id
    opcao_id = dados.opcao_origem_id or regra.opcao_origem_id
    destino_id = dados.pergunta_destino_id or regra.pergunta_destino_id

    if origem_id == destino_id:
        raise HTTPException(status_code=400, detail="Pergunta de origem e destino devem ser diferentes.")
    opcao = db.query(OpcaoPerguntaDiagnostico).filter(OpcaoPerguntaDiagnostico.id == opcao_id).first()
    if not opcao or opcao.pergunta_id != origem_id:
        raise HTTPException(status_code=400, detail="A opção de origem não pertence à pergunta de origem.")

    for pid in (origem_id, destino_id):
        existe = db.query(FormularioPergunta).filter(
            FormularioPergunta.formulario_id == regra.formulario_id,
            FormularioPergunta.pergunta_id == pid,
            FormularioPergunta.ativo.is_(True),
        ).first()
        if not existe:
            raise HTTPException(status_code=400, detail="Perguntas da regra devem estar ativas no formulário.")

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(regra, campo, valor)
    _commit(db)
    db.refresh(regra)
    return regra


@router.delete("/regras-exibicao/{regra_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_regra(regra_id: UUID, db: Session = Depends(get_db)):
    regra = _regra_ou_404(db, regra_id)
    db.delete(regra)
    _commit(db)
    return None
