from datetime import datetime, timezone
from decimal import Decimal
import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_platform_db, tenant_session
from app.models.diagnostico import (
    CategoriaDiagnostico,
    Diagnostico,
    FaixaAvaliacaoNumero,
    FormularioDiagnostico,
    FormularioPergunta,
    OpcaoPerguntaDiagnostico,
    PerguntaDiagnostico,
    RegraExibicaoPergunta,
    RespostaDiagnostico,
    RespostaDiagnosticoOpcao,
)
from app.models.platform_auth import PlatformTenant
from app.schemas.diagnostico_aplicacao import PreenchimentoPublicoInput, PreenchimentoPublicoResponse

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


def _carregar_estrutura(db: Session, aplicacao: Diagnostico):
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
    perguntas = {pergunta.id: (fp, pergunta, categoria) for fp, pergunta, categoria in linhas}
    regras = (
        db.query(RegraExibicaoPergunta)
        .filter(RegraExibicaoPergunta.formulario_id == formulario.id)
        .order_by(RegraExibicaoPergunta.created_at, RegraExibicaoPergunta.id)
        .all()
    )
    return formulario, linhas, perguntas, regras


def _opcoes_ativas(db: Session, pergunta_id: UUID):
    return (
        db.query(OpcaoPerguntaDiagnostico)
        .filter(
            OpcaoPerguntaDiagnostico.pergunta_id == pergunta_id,
            OpcaoPerguntaDiagnostico.ativo.is_(True),
        )
        .order_by(OpcaoPerguntaDiagnostico.ordem, OpcaoPerguntaDiagnostico.rotulo)
        .all()
    )


def _respostas_salvas(db: Session, aplicacao_id: UUID):
    respostas = db.query(RespostaDiagnostico).filter(
        RespostaDiagnostico.diagnostico_id == aplicacao_id
    ).all()
    multiplas = {}
    if respostas:
        ids = [r.id for r in respostas]
        for item in db.query(RespostaDiagnosticoOpcao).filter(
            RespostaDiagnosticoOpcao.resposta_id.in_(ids)
        ).all():
            multiplas.setdefault(item.resposta_id, []).append(item.opcao_id)
    return respostas, multiplas


def _ids_opcoes_por_resposta(perguntas, payload_por_pergunta):
    selecionadas = {}
    for pergunta_id, entrada in payload_por_pergunta.items():
        pergunta = perguntas[pergunta_id][1]
        tipo = str(pergunta.tipo_resposta or "").upper()
        if tipo == "ESCOLHA_UNICA" and entrada.opcao_id:
            selecionadas[pergunta_id] = {entrada.opcao_id}
        elif tipo == "MULTIPLA_ESCOLHA" and entrada.opcoes_ids:
            selecionadas[pergunta_id] = set(entrada.opcoes_ids)
    return selecionadas


def _perguntas_aplicaveis(perguntas, regras, selecionadas):
    destinos = {r.pergunta_destino_id for r in regras}
    visiveis = {pid for pid in perguntas if pid not in destinos}
    mudou = True
    while mudou:
        mudou = False
        for regra in regras:
            if regra.pergunta_origem_id not in visiveis:
                continue
            if regra.opcao_origem_id not in selecionadas.get(regra.pergunta_origem_id, set()):
                continue
            if regra.pergunta_destino_id in perguntas and regra.pergunta_destino_id not in visiveis:
                visiveis.add(regra.pergunta_destino_id)
                mudou = True
    return visiveis


def _validar_payload(db: Session, perguntas, dados: PreenchimentoPublicoInput):
    payload = {}
    for entrada in dados.respostas:
        if entrada.pergunta_id in payload:
            raise HTTPException(status_code=422, detail="A mesma pergunta foi enviada mais de uma vez.")
        if entrada.pergunta_id not in perguntas:
            raise HTTPException(status_code=422, detail="Foi enviada uma pergunta que não pertence ao formulário.")

        pergunta = perguntas[entrada.pergunta_id][1]
        tipo = str(pergunta.tipo_resposta or "").upper()
        opcoes = _opcoes_ativas(db, pergunta.id)
        opcoes_por_id = {o.id: o for o in opcoes}

        if tipo == "ESCOLHA_UNICA":
            if entrada.opcao_id is None or entrada.opcao_id not in opcoes_por_id:
                raise HTTPException(status_code=422, detail=f"Resposta inválida para a pergunta {pergunta.codigo or pergunta.id}.")
            if entrada.opcoes_ids or entrada.resposta_texto is not None or entrada.resposta_numero is not None:
                raise HTTPException(status_code=422, detail=f"Formato de resposta inválido para a pergunta {pergunta.codigo or pergunta.id}.")
        elif tipo == "MULTIPLA_ESCOLHA":
            if not entrada.opcoes_ids or any(oid not in opcoes_por_id for oid in entrada.opcoes_ids):
                raise HTTPException(status_code=422, detail=f"Resposta inválida para a pergunta {pergunta.codigo or pergunta.id}.")
            if len(set(entrada.opcoes_ids)) != len(entrada.opcoes_ids):
                raise HTTPException(status_code=422, detail=f"Há opções repetidas na pergunta {pergunta.codigo or pergunta.id}.")
            if entrada.opcao_id is not None or entrada.resposta_texto is not None or entrada.resposta_numero is not None:
                raise HTTPException(status_code=422, detail=f"Formato de resposta inválido para a pergunta {pergunta.codigo or pergunta.id}.")
        elif tipo == "NUMERO":
            if entrada.resposta_numero is None:
                raise HTTPException(status_code=422, detail=f"Resposta numérica inválida para a pergunta {pergunta.codigo or pergunta.id}.")
            if entrada.opcao_id is not None or entrada.opcoes_ids or entrada.resposta_texto is not None:
                raise HTTPException(status_code=422, detail=f"Formato de resposta inválido para a pergunta {pergunta.codigo or pergunta.id}.")
        elif tipo == "TEXTO_CURTO":
            texto = (entrada.resposta_texto or "").strip()
            if not texto:
                raise HTTPException(status_code=422, detail=f"Resposta de texto inválida para a pergunta {pergunta.codigo or pergunta.id}.")
            entrada.resposta_texto = texto
            if entrada.opcao_id is not None or entrada.opcoes_ids or entrada.resposta_numero is not None:
                raise HTTPException(status_code=422, detail=f"Formato de resposta inválido para a pergunta {pergunta.codigo or pergunta.id}.")
        else:
            raise HTTPException(status_code=422, detail=f"Tipo de resposta não suportado: {pergunta.tipo_resposta}.")
        payload[entrada.pergunta_id] = entrada
    return payload


def _estado_numero(db: Session, pergunta: PerguntaDiagnostico, valor: Decimal):
    if str(pergunta.natureza or "").upper() != "AVALIATIVA":
        return None
    faixas = db.query(FaixaAvaliacaoNumero).filter(
        FaixaAvaliacaoNumero.pergunta_id == pergunta.id
    ).all()
    correspondentes = [
        f for f in faixas
        if (f.valor_min is None or valor >= f.valor_min)
        and (f.valor_max is None or valor <= f.valor_max)
    ]
    if len(correspondentes) != 1:
        raise HTTPException(
            status_code=422,
            detail=f"A pergunta {pergunta.codigo or pergunta.id} não possui uma faixa de avaliação válida para o valor informado.",
        )
    return correspondentes[0].estado_interno


def _sincronizar_respostas(db: Session, aplicacao: Diagnostico, perguntas, aplicaveis, payload):
    existentes, _ = _respostas_salvas(db, aplicacao.id)
    existentes_por_pergunta = {r.pergunta_id: r for r in existentes}

    # O payload representa o estado atual completo das respostas do formulário.
    # Tudo que não está respondido ou deixou de ser aplicável é removido.
    manter = set(payload) & set(aplicaveis)
    for pergunta_id, resposta in list(existentes_por_pergunta.items()):
        if pergunta_id not in manter:
            db.delete(resposta)

    for pergunta_id in manter:
        entrada = payload[pergunta_id]
        pergunta = perguntas[pergunta_id][1]
        tipo = str(pergunta.tipo_resposta or "").upper()
        resposta = existentes_por_pergunta.get(pergunta_id)
        if resposta is None:
            resposta = RespostaDiagnostico(diagnostico_id=aplicacao.id, pergunta_id=pergunta_id)
            db.add(resposta)
            db.flush()

        resposta.opcao_id = None
        resposta.estado_interno = None
        resposta.resposta_texto = None
        resposta.resposta_numero = None
        resposta.resposta_boolean = None
        resposta.pontuacao = None

        db.query(RespostaDiagnosticoOpcao).filter(
            RespostaDiagnosticoOpcao.resposta_id == resposta.id
        ).delete(synchronize_session=False)

        if tipo == "ESCOLHA_UNICA":
            opcao = db.query(OpcaoPerguntaDiagnostico).filter(
                OpcaoPerguntaDiagnostico.id == entrada.opcao_id,
                OpcaoPerguntaDiagnostico.pergunta_id == pergunta_id,
                OpcaoPerguntaDiagnostico.ativo.is_(True),
            ).first()
            resposta.opcao_id = opcao.id
            resposta.estado_interno = opcao.estado_interno
        elif tipo == "MULTIPLA_ESCOLHA":
            for opcao_id in entrada.opcoes_ids:
                db.add(RespostaDiagnosticoOpcao(resposta_id=resposta.id, opcao_id=opcao_id))
        elif tipo == "NUMERO":
            resposta.resposta_numero = entrada.resposta_numero
            resposta.estado_interno = _estado_numero(db, pergunta, entrada.resposta_numero)
        elif tipo == "TEXTO_CURTO":
            resposta.resposta_texto = entrada.resposta_texto


def _processar_preenchimento(db: Session, token: str, dados: PreenchimentoPublicoInput, finalizar: bool):
    aplicacao = _aplicacao_valida(db, token)
    _, _, perguntas, regras = _carregar_estrutura(db, aplicacao)
    payload = _validar_payload(db, perguntas, dados)
    selecionadas = _ids_opcoes_por_resposta(perguntas, payload)
    aplicaveis = _perguntas_aplicaveis(perguntas, regras, selecionadas)

    indevidas = set(payload) - aplicaveis
    if indevidas:
        raise HTTPException(status_code=422, detail="Foram enviadas respostas para perguntas que não estão aplicáveis.")

    if finalizar:
        faltantes = [
            pergunta.codigo or str(pergunta.id)
            for pid, (fp, pergunta, _) in perguntas.items()
            if pid in aplicaveis and fp.obrigatoria and pid not in payload
        ]
        if faltantes:
            raise HTTPException(
                status_code=422,
                detail="Existem perguntas obrigatórias sem resposta: " + ", ".join(faltantes),
            )

    try:
        _sincronizar_respostas(db, aplicacao, perguntas, aplicaveis, payload)
        aplicacao.status = "RESPONDIDO" if finalizar else "EM_PREENCHIMENTO"
        aplicacao.concluido_em = datetime.now(timezone.utc) if finalizar else None
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    return PreenchimentoPublicoResponse(
        status=aplicacao.status,
        respondidas=len(payload),
        aplicaveis=len(aplicaveis),
        concluido_em=aplicacao.concluido_em,
    )


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
        formulario, linhas, _, regras = _carregar_estrutura(db, aplicacao)

        perguntas_publicas = []
        for fp, pergunta, categoria in linhas:
            opcoes = _opcoes_ativas(db, pergunta.id)
            perguntas_publicas.append({
                "id": str(pergunta.id),
                "codigo": pergunta.codigo,
                "pergunta": pergunta.pergunta,
                "ajuda": pergunta.ajuda,
                "tipo_resposta": pergunta.tipo_resposta,
                "categoria": categoria.nome,
                "obrigatoria": fp.obrigatoria,
                "opcoes": [{"id": str(o.id), "valor": o.valor, "rotulo": o.rotulo} for o in opcoes],
            })

        respostas, multiplas = _respostas_salvas(db, aplicacao.id)
        respostas_publicas = []
        for resposta in respostas:
            item = {"pergunta_id": str(resposta.pergunta_id)}
            if resposta.opcao_id:
                item["opcao_id"] = str(resposta.opcao_id)
            if resposta.id in multiplas:
                item["opcoes_ids"] = [str(v) for v in multiplas[resposta.id]]
            if resposta.resposta_texto is not None:
                item["resposta_texto"] = resposta.resposta_texto
            if resposta.resposta_numero is not None:
                item["resposta_numero"] = str(resposta.resposta_numero)
            respostas_publicas.append(item)

        return {
            "formulario": {
                "nome": formulario.nome,
                "descricao": formulario.descricao,
                "versao": formulario.versao,
            },
            "aplicacao": {
                "contato_nome": aplicacao.nome_contato,
                "status": aplicacao.status,
                "token_expira_em": aplicacao.token_expira_em,
            },
            "perguntas": perguntas_publicas,
            "regras_exibicao": [
                {
                    "pergunta_origem_id": str(regra.pergunta_origem_id),
                    "opcao_origem_id": str(regra.opcao_origem_id),
                    "pergunta_destino_id": str(regra.pergunta_destino_id),
                }
                for regra in regras
            ],
            "respostas": respostas_publicas,
        }


@router.put("/{token}/respostas", response_model=PreenchimentoPublicoResponse)
def salvar_respostas_publicas(
    token: str,
    dados: PreenchimentoPublicoInput,
    platform_db: Session = Depends(get_platform_db),
):
    tenant_id = _tenant_id_do_token(token)
    tenant = platform_db.query(PlatformTenant).filter(
        PlatformTenant.id == tenant_id,
        PlatformTenant.ativo.is_(True),
    ).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Acesso inválido.")
    with tenant_session(platform_db, tenant_id) as db:
        return _processar_preenchimento(db, token, dados, finalizar=False)


@router.post("/{token}/finalizar", response_model=PreenchimentoPublicoResponse)
def finalizar_respostas_publicas(
    token: str,
    dados: PreenchimentoPublicoInput,
    platform_db: Session = Depends(get_platform_db),
):
    tenant_id = _tenant_id_do_token(token)
    tenant = platform_db.query(PlatformTenant).filter(
        PlatformTenant.id == tenant_id,
        PlatformTenant.ativo.is_(True),
    ).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Acesso inválido.")
    with tenant_session(platform_db, tenant_id) as db:
        return _processar_preenchimento(db, token, dados, finalizar=True)
