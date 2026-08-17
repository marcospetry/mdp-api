from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.contato import Contato
from app.models.interacao import Interacao
from app.schemas.contato import ContatoCreate, ContatoResponse
from app.services.email_service import (
    enviar_email_confirmacao_contato,
    enviar_email_novo_contato,
)


router = APIRouter(
    prefix="/api/contatos",
    tags=["Contatos"],
)

MDP_EMPRESA_ID = UUID(
    "4ac04902-ee2b-4b18-b99a-b5b3bbefaa40"
)


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
    contato = Contato(
        empresa_id=MDP_EMPRESA_ID,

        nome=dados.nome,
        email=str(dados.email),
        telefone=dados.telefone,
        empresa_contato=dados.empresa_contato,
        mensagem=dados.mensagem,

        origem="site",
        origem_primeiro_contato="site",
        origem_ultimo_contato="site",
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
        empresa_id=MDP_EMPRESA_ID,
        contato_id=contato.id,
        canal="SITE",
        origem="formulario_site",
        tipo_interacao="FORMULARIO_SITE",
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
