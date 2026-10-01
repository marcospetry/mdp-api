from datetime import datetime, timezone
import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_platform_db, tenant_session
from app.models.diagnostico import (
    CategoriaDiagnostico,
    Diagnostico,
    FormularioDiagnostico,
    FormularioPergunta,
    OpcaoPerguntaDiagnostico,
    PerguntaDiagnostico,
    RegraExibicaoPergunta,
)
from app.models.platform_auth import PlatformTenant

router = APIRouter(prefix="/api/publico/diagnostico", tags=["Diagnóstico - Público"])


def _tenant_id_do_token(token: str) -> UUID:
    prefixo, separador, segredo = token.partition(".")
    if not separador or not segredo:
        raise HTTPException(status_code=404, detail="Acesso inválido.")
    try:
        return UUID(prefixo)
    except ValueError:
        raise HTTPException(status_code=404, detail="Acesso inválido.")


def _aplicacao_valida(db: Session, token: str) -> Diagnostico:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    aplicacao = db.query(Diagnostico).filter(Diagnostico.token_hash == token_hash).first()
    if not aplicacao:
        raise HTTPException(status_code=404, detail="Acesso inválido.")
    if aplicacao.token_revogado_em is not None:
        raise HTTPException(status_code=410, detail="Este acesso foi revogado.")
    if aplicacao.token_expira_em is None or aplicacao.token_expira_em <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Este acesso expirou.")
    if str(aplicacao.status or "").upper() == "RESPONDIDO":
        raise HTTPException(status_code=409, detail="Este diagnóstico já foi respondido.")
    return aplicacao


@router.get("/{token}")
def obter_formulario_publico(token: str, platform_db: Session = Depends(get_platform_db)):
    tenant_id = _tenant_id_do_token(token)
    tenant = platform_db.query(PlatformTenant).filter(
        PlatformTenant.id == tenant_id,
        PlatformTenant.ativo.is_(True),
    ).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Acesso inválido.")

    with tenant_session(platform_db, tenant_id) as db:
        aplicacao = _aplicacao_valida(db, token)
        formulario = db.query(FormularioDiagnostico).filter(
            FormularioDiagnostico.id == aplicacao.formulario_id
        ).first()
        if not formulario:
            raise HTTPException(status_code=404, detail="Formulário não encontrado.")

        linhas = (
            db.query(FormularioPergunta, PerguntaDiagnostico, CategoriaDiagnostico)
            .join(PerguntaDiagnostico, PerguntaDiagnostico.id == FormularioPergunta.pergunta_id)
            .join(CategoriaDiagnostico, CategoriaDiagnostico.id == PerguntaDiagnostico.categoria_id)
            .filter(
                FormularioPergunta.formulario_id == formulario.id,
                FormularioPergunta.ativo.is_(True),
                PerguntaDiagnostico.ativo.is_(True),
            )
            .order_by(FormularioPergunta.ordem, PerguntaDiagnostico.codigo)
            .all()
        )

        perguntas = []
        for fp, pergunta, categoria in linhas:
            opcoes = (
                db.query(OpcaoPerguntaDiagnostico)
                .filter(
                    OpcaoPerguntaDiagnostico.pergunta_id == pergunta.id,
                    OpcaoPerguntaDiagnostico.ativo.is_(True),
                )
                .order_by(OpcaoPerguntaDiagnostico.ordem, OpcaoPerguntaDiagnostico.rotulo)
                .all()
            )
            perguntas.append({
                "id": str(pergunta.id),
                "codigo": pergunta.codigo,
                "pergunta": pergunta.pergunta,
                "tipo_resposta": pergunta.tipo_resposta,
                "categoria": categoria.nome,
                "obrigatoria": fp.obrigatoria,
                "opcoes": [{"id": str(o.id), "valor": o.valor, "rotulo": o.rotulo} for o in opcoes],
            })

        regras = (
            db.query(RegraExibicaoPergunta)
            .filter(RegraExibicaoPergunta.formulario_id == formulario.id)
            .order_by(RegraExibicaoPergunta.created_at, RegraExibicaoPergunta.id)
            .all()
        )

        return {
            "formulario": {
                "nome": formulario.nome,
                "descricao": formulario.descricao,
                "versao": formulario.versao,
            },
            "aplicacao": {
                "contato_nome": aplicacao.nome_contato,
                "token_expira_em": aplicacao.token_expira_em,
            },
            "perguntas": perguntas,
            "regras_exibicao": [
                {
                    "pergunta_origem_id": str(regra.pergunta_origem_id),
                    "opcao_origem_id": str(regra.opcao_origem_id),
                    "pergunta_destino_id": str(regra.pergunta_destino_id),
                }
                for regra in regras
            ],
        }
