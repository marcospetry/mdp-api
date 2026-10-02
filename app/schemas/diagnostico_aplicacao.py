from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class AplicacaoDiagnosticoCreate(BaseModel):
    contato_id: UUID
    formulario_id: UUID


class AplicacaoAcessoCreate(BaseModel):
    dias_validade: int = Field(default=7, ge=1, le=30)


class AplicacaoAcessoGeradoResponse(BaseModel):
    aplicacao_id: UUID
    token: str
    caminho_publico: str
    token_expira_em: datetime


class AplicacaoDiagnosticoResponse(BaseModel):
    id: UUID
    empresa_id: UUID
    contato_id: UUID | None
    contato_nome: str | None
    formulario_id: UUID | None
    formulario_nome: str | None
    formulario_codigo: str | None
    formulario_versao: int | None
    status: str
    iniciado_em: datetime
    concluido_em: datetime | None
    created_at: datetime
    acesso_gerado: bool = False
    token_expira_em: datetime | None = None
    token_revogado_em: datetime | None = None
    acesso_expirado: bool = False


class AplicacaoRespostaOpcaoResponse(BaseModel):
    id: UUID
    valor: str
    rotulo: str
    estado_interno: str | None = None
    selecionada: bool = False


class AplicacaoRespostaFaixaResponse(BaseModel):
    valor_min: Decimal | None = None
    valor_max: Decimal | None = None
    estado_interno: str
    correspondente: bool = False


class AplicacaoRespostaPerguntaResponse(BaseModel):
    pergunta_id: UUID
    codigo: str | None = None
    pergunta: str
    tipo_resposta: str
    natureza: str
    obrigatoria: bool = False
    categoria_id: UUID
    categoria_nome: str
    categoria_ordem: int = 0
    ordem: int = 0
    respondida: bool = False
    aplicavel: bool = True
    estado_interno: str | None = None
    resposta_texto: str | None = None
    resposta_numero: Decimal | None = None
    opcoes: list[AplicacaoRespostaOpcaoResponse] = Field(default_factory=list)
    faixas: list[AplicacaoRespostaFaixaResponse] = Field(default_factory=list)


class AplicacaoRespostasResponse(BaseModel):
    aplicacao_id: UUID
    contato_nome: str | None = None
    formulario_nome: str | None = None
    formulario_codigo: str | None = None
    formulario_versao: int | None = None
    status: str
    concluido_em: datetime | None = None
    respondidas: int = 0
    aplicaveis: int = 0
    perguntas: list[AplicacaoRespostaPerguntaResponse] = Field(default_factory=list)


class RespostaPublicaInput(BaseModel):
    pergunta_id: UUID
    opcao_id: UUID | None = None
    opcoes_ids: list[UUID] = Field(default_factory=list)
    resposta_texto: str | None = None
    resposta_numero: Decimal | None = None


class PreenchimentoPublicoInput(BaseModel):
    respostas: list[RespostaPublicaInput] = Field(default_factory=list)


class PreenchimentoPublicoResponse(BaseModel):
    status: str
    respondidas: int
    aplicaveis: int
    concluido_em: datetime | None = None
