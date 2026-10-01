from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.models.contato import Contato
from app.models.diagnostico import Diagnostico, FormularioDiagnostico, FormularioPergunta
from app.models.empresa import Empresa
from app.schemas.diagnostico_aplicacao import (
    AplicacaoAcessoCreate,
    AplicacaoAcessoGeradoResponse,
    AplicacaoDiagnosticoCreate,
    AplicacaoDiagnosticoResponse,
)
from app.security.dependencies import (
    get_authorized_tenant_db as get_db,
    get_current_context,
    require_empresa_access,
    require_tenant_context,
)


router = APIRouter(
    prefix="/api/diagnostico/aplicacoes",
    tags=["Diagnóstico - Aplicações"],
    dependencies=[Depends(require_tenant_context)],
)


def _response(db: Session, diagnostico: Diagnostico) -> AplicacaoDiagnosticoResponse:
    contato = (
        db.query(Contato).filter(Contato.id == diagnostico.contato_id).first()
        if diagnostico.contato_id
        else None
    )
    formulario = (
        db.query(FormularioDiagnostico)
        .filter(FormularioDiagnostico.id == diagnostico.formulario_id)
        .first()
        if diagnostico.formulario_id
        else None
    )
    return AplicacaoDiagnosticoResponse(
        id=diagnostico.id,
        empresa_id=diagnostico.empresa_id,
        contato_id=diagnostico.contato_id,
        contato_nome=contato.nome if contato else diagnostico.nome_contato,
        formulario_id=diagnostico.formulario_id,
        formulario_nome=formulario.nome if formulario else None,
        formulario_codigo=formulario.codigo if formulario else None,
        formulario_versao=formulario.versao if formulario else None,
        status=diagnostico.status,
        iniciado_em=diagnostico.iniciado_em,
        concluido_em=diagnostico.concluido_em,
        created_at=diagnostico.created_at,
        acesso_gerado=bool(diagnostico.token_hash),
        token_expira_em=diagnostico.token_expira_em,
        token_revogado_em=diagnostico.token_revogado_em,
        acesso_expirado=bool(
            diagnostico.token_expira_em
            and diagnostico.token_expira_em <= datetime.now(timezone.utc)
        ),
    )


@router.get("", response_model=list[AplicacaoDiagnosticoResponse])
def listar_aplicacoes(
    contato_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    context=Depends(get_current_context),
):
    query = db.query(Diagnostico).filter(
        Diagnostico.contato_id.is_not(None),
        Diagnostico.formulario_id.is_not(None),
    )

    if contato_id is not None:
        contato = db.query(Contato).filter(Contato.id == contato_id).first()
        if not contato:
            raise HTTPException(status_code=404, detail="Contato não encontrado.")
        require_empresa_access(context, contato.empresa_id)
        query = query.filter(Diagnostico.contato_id == contato_id)
    elif not context["usuario"].is_superadmin:
        if not context.get("empresa_id"):
            return []
        query = query.filter(Diagnostico.empresa_id == context["empresa_id"])

    aplicacoes = query.order_by(Diagnostico.created_at.desc()).all()
    return [_response(db, item) for item in aplicacoes]


@router.post("", response_model=AplicacaoDiagnosticoResponse, status_code=status.HTTP_201_CREATED)
def atribuir_formulario(
    dados: AplicacaoDiagnosticoCreate,
    db: Session = Depends(get_db),
    context=Depends(get_current_context),
):
    contato = db.query(Contato).filter(Contato.id == dados.contato_id).first()
    if not contato:
        raise HTTPException(status_code=404, detail="Contato não encontrado.")
    require_empresa_access(context, contato.empresa_id)

    formulario = (
        db.query(FormularioDiagnostico)
        .filter(FormularioDiagnostico.id == dados.formulario_id)
        .first()
    )
    if not formulario:
        raise HTTPException(status_code=404, detail="Formulário não encontrado.")

    # Uma aplicação só pode usar um formulário global ou um formulário
    # pertencente à mesma empresa do contato.
    if formulario.empresa_id is not None and formulario.empresa_id != contato.empresa_id:
        raise HTTPException(
            status_code=403,
            detail="O formulário selecionado não está disponível para a empresa deste contato.",
        )

    if not formulario.ativo:
        raise HTTPException(status_code=409, detail="O formulário selecionado está inativo.")

    total_perguntas = (
        db.query(FormularioPergunta.id)
        .filter(
            FormularioPergunta.formulario_id == formulario.id,
            FormularioPergunta.ativo.is_(True),
        )
        .count()
    )
    if total_perguntas == 0:
        raise HTTPException(
            status_code=409,
            detail="O formulário selecionado não possui perguntas ativas atribuídas.",
        )

    empresa = db.query(Empresa).filter(Empresa.id == contato.empresa_id).first()

    aplicacao = Diagnostico(
        empresa_id=contato.empresa_id,
        contato_id=contato.id,
        formulario_id=formulario.id,
        nome_contato=contato.nome,
        email_contato=contato.email,
        telefone_contato=contato.telefone,
        empresa_avaliada=contato.empresa_contato or (empresa.nome if empresa else None),
        status="AGUARDANDO_RESPOSTA",
    )
    db.add(aplicacao)
    db.commit()
    db.refresh(aplicacao)

    return _response(db, aplicacao)


@router.post("/{aplicacao_id}/acesso", response_model=AplicacaoAcessoGeradoResponse)
def gerar_acesso_publico(
    aplicacao_id: UUID,
    dados: AplicacaoAcessoCreate,
    db: Session = Depends(get_db),
    context=Depends(get_current_context),
):
    aplicacao = db.query(Diagnostico).filter(Diagnostico.id == aplicacao_id).first()
    if not aplicacao:
        raise HTTPException(status_code=404, detail="Aplicação não encontrada.")
    require_empresa_access(context, aplicacao.empresa_id)
    if not aplicacao.formulario_id or not aplicacao.contato_id:
        raise HTTPException(status_code=409, detail="Aplicação não possui contato e formulário atribuídos.")
    if _status_normalizado(aplicacao.status) == "RESPONDIDO":
        raise HTTPException(status_code=409, detail="Aplicação já respondida não pode receber novo acesso.")

    segredo = secrets.token_urlsafe(32)
    token = f"{context['tenant_id']}.{segredo}"
    aplicacao.token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    aplicacao.token_expira_em = datetime.now(timezone.utc) + timedelta(days=dados.dias_validade)
    aplicacao.token_revogado_em = None
    if _status_normalizado(aplicacao.status) == "REVOGADO":
        aplicacao.status = "AGUARDANDO_RESPOSTA"
    db.commit()
    db.refresh(aplicacao)
    return AplicacaoAcessoGeradoResponse(
        aplicacao_id=aplicacao.id,
        token=token,
        caminho_publico=f"/diagnostico/responder/{token}",
        token_expira_em=aplicacao.token_expira_em,
    )


@router.post("/{aplicacao_id}/revogar-acesso", response_model=AplicacaoDiagnosticoResponse)
def revogar_acesso_publico(
    aplicacao_id: UUID,
    db: Session = Depends(get_db),
    context=Depends(get_current_context),
):
    aplicacao = db.query(Diagnostico).filter(Diagnostico.id == aplicacao_id).first()
    if not aplicacao:
        raise HTTPException(status_code=404, detail="Aplicação não encontrada.")
    require_empresa_access(context, aplicacao.empresa_id)
    if not aplicacao.token_hash:
        raise HTTPException(status_code=409, detail="Esta aplicação ainda não possui acesso público.")
    aplicacao.token_revogado_em = datetime.now(timezone.utc)
    aplicacao.status = "REVOGADO"
    db.commit()
    db.refresh(aplicacao)
    return _response(db, aplicacao)


def _status_normalizado(value) -> str:
    return str(value or "").upper()
