from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

TipoResposta = Literal["ESCOLHA_UNICA", "MULTIPLA_ESCOLHA", "NUMERO", "TEXTO_CURTO"]
NaturezaPergunta = Literal["AVALIATIVA", "CONTEXTO"]
EstadoInterno = Literal["ALTO", "MEDIO", "BAIXO", "NA", "NAO_SEI"]


class CategoriaBase(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    descricao: str | None = None
    ordem: int = 0
    ativo: bool = True
    empresa_id: UUID | None = None


class CategoriaCreate(CategoriaBase):
    pass


class CategoriaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    descricao: str | None = None
    ordem: int | None = None
    ativo: bool | None = None


class CategoriaResponse(CategoriaBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OpcaoBase(BaseModel):
    valor: str = Field(min_length=1, max_length=80)
    rotulo: str = Field(min_length=1, max_length=150)
    estado_interno: EstadoInterno | None = None
    pontuacao: Decimal = Decimal("0")
    ordem: int = 0
    ativo: bool = True


class OpcaoCreate(OpcaoBase):
    pass


class OpcaoUpdate(BaseModel):
    valor: str | None = Field(default=None, min_length=1, max_length=80)
    rotulo: str | None = Field(default=None, min_length=1, max_length=150)
    estado_interno: EstadoInterno | None = None
    pontuacao: Decimal | None = None
    ordem: int | None = None
    ativo: bool | None = None


class OpcaoResponse(OpcaoBase):
    id: UUID
    pergunta_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FaixaBase(BaseModel):
    valor_min: Decimal | None = None
    valor_max: Decimal | None = None
    estado_interno: EstadoInterno

    @model_validator(mode="after")
    def validar_limites(self):
        if self.valor_min is not None and self.valor_max is not None and self.valor_min > self.valor_max:
            raise ValueError("valor_min deve ser menor ou igual a valor_max")
        return self


class FaixaCreate(FaixaBase):
    pass


class FaixaUpdate(BaseModel):
    valor_min: Decimal | None = None
    valor_max: Decimal | None = None
    estado_interno: EstadoInterno | None = None


class FaixaResponse(FaixaBase):
    id: UUID
    pergunta_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PerguntaBase(BaseModel):
    categoria_id: UUID
    codigo: str | None = Field(default=None, max_length=30)
    pergunta: str = Field(min_length=1)
    tipo_resposta: TipoResposta
    natureza: NaturezaPergunta = "CONTEXTO"
    ideal: str | None = None
    sugestao: str | None = None

    # Legado mantido temporariamente por compatibilidade.
    peso: Decimal = Decimal("1")
    ordem: int = 0
    obrigatoria: bool = False
    metodo_avaliacao: str = Field(default="cliente", max_length=20)
    ajuda: str | None = None
    gera_achado: bool = True
    ativo: bool = True
    empresa_id: UUID | None = None

    @model_validator(mode="after")
    def validar_tipo_natureza(self):
        if self.tipo_resposta in {"MULTIPLA_ESCOLHA", "TEXTO_CURTO"} and self.natureza != "CONTEXTO":
            raise ValueError(f"{self.tipo_resposta} deve usar natureza CONTEXTO")
        if self.natureza == "AVALIATIVA":
            if not self.ideal or not self.ideal.strip():
                raise ValueError("Pergunta AVALIATIVA exige campo ideal")
            if not self.sugestao or not self.sugestao.strip():
                raise ValueError("Pergunta AVALIATIVA exige campo sugestao")
        return self


class PerguntaCreate(PerguntaBase):
    opcoes: list[OpcaoCreate] = Field(default_factory=list)
    faixas: list[FaixaCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validar_entradas_por_tipo(self):
        if self.tipo_resposta in {"NUMERO", "TEXTO_CURTO"} and self.opcoes:
            raise ValueError(f"Pergunta {self.tipo_resposta} não utiliza opções")
        if self.tipo_resposta != "NUMERO" and self.faixas:
            raise ValueError("Somente pergunta NUMERO utiliza faixas")
        if self.tipo_resposta == "NUMERO" and self.natureza != "AVALIATIVA" and self.faixas:
            raise ValueError("Faixas são permitidas apenas para NUMERO AVALIATIVA")
        return self


class PerguntaUpdate(BaseModel):
    categoria_id: UUID | None = None
    codigo: str | None = Field(default=None, max_length=30)
    pergunta: str | None = Field(default=None, min_length=1)
    tipo_resposta: TipoResposta | None = None
    natureza: NaturezaPergunta | None = None
    ideal: str | None = None
    sugestao: str | None = None
    peso: Decimal | None = None
    ordem: int | None = None
    obrigatoria: bool | None = None
    metodo_avaliacao: str | None = Field(default=None, max_length=20)
    ajuda: str | None = None
    gera_achado: bool | None = None
    ativo: bool | None = None


class PerguntaResponse(PerguntaBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PerguntaDetalheResponse(PerguntaResponse):
    categoria_nome: str
    opcoes: list[OpcaoResponse] = Field(default_factory=list)
    faixas: list[FaixaResponse] = Field(default_factory=list)


class FormularioBase(BaseModel):
    codigo: str = Field(min_length=1, max_length=50)
    nome: str = Field(min_length=1, max_length=150)
    descricao: str | None = None
    tipo: str = Field(min_length=1, max_length=50)
    versao: int = Field(default=1, ge=1)
    ativo: bool = True
    empresa_id: UUID | None = None


class FormularioCreate(FormularioBase):
    pass


class FormularioUpdate(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=50)
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    descricao: str | None = None
    tipo: str | None = Field(default=None, min_length=1, max_length=50)
    versao: int | None = Field(default=None, ge=1)
    ativo: bool | None = None


class FormularioResponse(FormularioBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FormularioPerguntaCreate(BaseModel):
    pergunta_id: UUID
    ordem: int = 0
    obrigatoria: bool = False
    peso: Decimal = Field(default=Decimal("1"), ge=0)
    ativo: bool = True


class FormularioPerguntaUpdate(BaseModel):
    ordem: int | None = None
    obrigatoria: bool | None = None
    peso: Decimal | None = Field(default=None, ge=0)
    ativo: bool | None = None


class FormularioPerguntaResponse(BaseModel):
    id: UUID
    formulario_id: UUID
    pergunta_id: UUID
    ordem: int
    obrigatoria: bool
    peso: Decimal
    ativo: bool
    codigo: str | None
    pergunta: str
    categoria_id: UUID
    categoria_nome: str
    tipo_resposta: TipoResposta
    natureza: NaturezaPergunta


class OrdenacaoItem(BaseModel):
    pergunta_id: UUID
    ordem: int = Field(ge=0)


class OrdenacaoFormulariosRequest(BaseModel):
    itens: list[OrdenacaoItem] = Field(min_length=1)


class RegraExibicaoBase(BaseModel):
    pergunta_origem_id: UUID
    opcao_origem_id: UUID
    pergunta_destino_id: UUID


class RegraExibicaoCreate(RegraExibicaoBase):
    pass


class RegraExibicaoUpdate(BaseModel):
    pergunta_origem_id: UUID | None = None
    opcao_origem_id: UUID | None = None
    pergunta_destino_id: UUID | None = None


class RegraExibicaoResponse(RegraExibicaoBase):
    id: UUID
    formulario_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FormularioDetalheResponse(FormularioResponse):
    perguntas: list[FormularioPerguntaResponse] = Field(default_factory=list)
    regras_exibicao: list[RegraExibicaoResponse] = Field(default_factory=list)


class MetadadosDiagnosticoResponse(BaseModel):
    tipos_resposta: list[str]
    naturezas: list[str]
    estados_internos: list[str]
