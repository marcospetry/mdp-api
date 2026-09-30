from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_platform_db, tenant_session
from app.models.contato import Contato
from app.models.empresa import Empresa
from app.models.interacao import Interacao
from app.models.manutencao import OrigemContato, TipoInteracao
from app.models.platform_auth import PlatformTenantEndpoint
from app.schemas.contato import ContatoCreate, ContatoResponse
from app.services.email_service import (
    enviar_email_confirmacao_contato,
    enviar_email_novo_contato,
)


router = APIRouter(
    prefix="/api/contatos",
    tags=["Contatos"],
)

FORM_CONTATO_ENDPOINT_CODE = "FORM_CONTATO_MDP"


@router.post(
    "",
    response_model=ContatoResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_contato(
    dados: ContatoCreate,
    background_tasks: BackgroundTasks,
    platform_db: Session = Depends(get_platform_db),
):
    endpoint = (
        platform_db.query(PlatformTenantEndpoint)
        .filter(
            PlatformTenantEndpoint.codigo == FORM_CONTATO_ENDPOINT_CODE,
            PlatformTenantEndpoint.ativo.is_(True),
        )
        .first()
    )
    if not endpoint:
        raise HTTPException(
            status_code=500,
            detail="Endpoint público de contato não configurado.",
        )

    configuracao = endpoint.configuracao or {}
    empresa_slug = configuracao.get("empresa_slug")
    if not empresa_slug:
        raise HTTPException(
            status_code=500,
            detail="Empresa destinatária não configurada para o endpoint.",
        )

    with tenant_session(platform_db, endpoint.tenant_id) as db:
        return _criar_contato_no_tenant(dados, background_tasks, db, platform_db, empresa_slug)


def _criar_contato_no_tenant(dados, background_tasks, db, platform_db, empresa_slug):
    empresa_inicial = (
        db.query(Empresa)
        .filter(
            Empresa.slug == empresa_slug,
            Empresa.ativo.is_(True),
        )
        .first()
    )
    if not empresa_inicial:
        raise HTTPException(
            status_code=500,
            detail="Empresa destinatária do endpoint não encontrada no tenant.",
        )

    codigo_origem = "OMNI" if dados.canal == "OMNI" else "SITE"
    codigo_tipo_interacao = "OMNI_AGENDAMENTO" if dados.canal == "OMNI" else "FORMULARIO_SITE"

    origem_obj = db.query(OrigemContato).filter(OrigemContato.codigo == codigo_origem, OrigemContato.ativo.is_(True)).first()
    if not origem_obj:
        raise HTTPException(
            status_code=500,
            detail=f"Origem de contato {codigo_origem} não configurada no tenant.",
        )

    tipo_obj = db.query(TipoInteracao).filter(TipoInteracao.codigo == codigo_tipo_interacao, TipoInteracao.ativo.is_(True)).first()
    if not tipo_obj:
        raise HTTPException(
            status_code=500,
            detail=f"Tipo de interação {codigo_tipo_interacao} não configurado no tenant.",
        )

    # Regra Dual-DB: o endpoint público resolve a organização destinatária
    # dentro do Tenant. O contato nasce vinculado a essa organização principal.
    # A empresa declarada pelo visitante permanece em empresa_contato até que
    # seja cadastrada como organização e o contato seja então revinculado.

    contato = Contato(
        empresa_id=empresa_inicial.id,
        origem_contato_id=origem_obj.id,

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
        tipo_interacao_id=tipo_obj.id,
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
