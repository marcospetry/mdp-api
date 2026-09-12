from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.contato import Contato
from app.models.empresa import Empresa
from app.models.interacao import Interacao
from app.models.manutencao import OrigemContato, TipoInteracao
from app.schemas.contato import ContatoCreate, ContatoResponse
from app.services.email_service import (
    enviar_email_confirmacao_contato,
    enviar_email_novo_contato,
)


router = APIRouter(
    prefix="/api/contatos",
    tags=["Contatos"],
)

SEM_EMPRESA_SLUG = "sem-empresa"


@router.post(
    "",
    response_model=ContatoResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_contato(
    dados: ContatoCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    empresa_inicial = (
        db.query(Empresa)
        .filter(Empresa.slug == SEM_EMPRESA_SLUG)
        .first()
    )
    if not empresa_inicial:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=500,
            detail="Empresa técnica 'sem-empresa' não encontrada.",
        )

    codigo_origem = "OMNI" if dados.canal == "OMNI" else "SITE"
    codigo_tipo_interacao = "OMNI_AGENDAMENTO" if dados.canal == "OMNI" else "FORMULARIO_SITE"

    origem_obj = db.query(OrigemContato).filter(OrigemContato.empresa_id.is_(None), OrigemContato.codigo == codigo_origem, OrigemContato.ativo.is_(True)).first()
    tipo_obj = db.query(TipoInteracao).filter(TipoInteracao.empresa_id.is_(None), TipoInteracao.codigo == codigo_tipo_interacao, TipoInteracao.ativo.is_(True)).first()

    contato = Contato(
        empresa_id=empresa_inicial.id,
        origem_contato_id=origem_obj.id if origem_obj else None,

        nome=dados.nome,
        email=str(dados.email),
        telefone=dados.telefone,
        empresa_contato=dados.empresa_contato,
        mensagem=dados.mensagem,

        origem=dados.canal.lower(),
        origem_primeiro_contato=dados.canal.lower(),
        origem_ultimo_contato=dados.canal.lower(),
        status="novo",

        tipo_solicitacao=dados.tipo_solicitacao,
        cnpj=dados.cnpj,
        cidade=dados.cidade,
        uf=dados.uf,
        site_instagram=dados.site_instagram,
        segmento=dados.segmento,
        objetivos=dados.objetivos or None,

        consentimento_dados=dados.consentimento_dados,
        consentimento_em=datetime.now(timezone.utc),
        consentimento_versao=dados.consentimento_versao,
    )

    db.add(contato)

    # Precisamos do UUID do contato para criar a interação, mas ainda não
    # queremos confirmar a transação. O flush executa o INSERT e mantém
    # contato + interação dentro da mesma unidade atômica.
    db.flush()

    interacao = Interacao(
        empresa_id=empresa_inicial.id,
        contato_id=contato.id,
        canal=dados.canal,
        origem=codigo_tipo_interacao.lower(),
        tipo_interacao_id=tipo_obj.id if tipo_obj else None,
        tipo_interacao=codigo_tipo_interacao,
        mensagem=dados.mensagem,
        direcao="ENTRADA",
        classificacao=dados.tipo_solicitacao,
    )

    db.add(interacao)

    # Um único commit evita contato sem interação caso algum dos INSERTs
    # falhe. Os e-mails continuam sendo disparados somente após o sucesso.
    db.commit()
    db.refresh(contato)

    background_tasks.add_task(
        enviar_email_novo_contato,
        contato,
    )

    background_tasks.add_task(
        enviar_email_confirmacao_contato,
        contato,
    )

    return contato
