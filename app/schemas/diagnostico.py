from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


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
    pontuacao: Decimal = Decimal("0")
    ordem: int = 0
    ativo: bool = True


class OpcaoCreate(OpcaoBase):
    pass


class OpcaoUpdate(BaseModel):
    valor: str | None = Field(default=None, min_length=1, max_length=80)
    rotulo: str | None = Field(default=None, min_length=1, max_length=150)
    pontuacao: Decimal | None = None
    ordem: int | None = None
    ativo: bool | None = None


class OpcaoResponse(OpcaoBase):
    id: UUID
    pergunta_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PerguntaBase(BaseModel):
    categoria_id: UUID
    codigo: str | None = Field(default=None, max_length=30)
    pergunta: str = Field(min_length=1)
    tipo_resposta: str = Field(min_length=1, max_length=30)
    peso: Decimal = Decimal("1")
    ordem: int = 0
    obrigatoria: bool = False
    metodo_avaliacao: str = Field(default="cliente", max_length=20)
    ajuda: str | None = None
    gera_achado: bool = True
    ativo: bool = True
    empresa_id: UUID | None = None


class PerguntaCreate(PerguntaBase):
    opcoes: list[OpcaoCreate] = Field(default_factory=list)


class PerguntaUpdate(BaseModel):
    categoria_id: UUID | None = None
    codigo: str | None = Field(default=None, max_length=30)
    pergunta: str | None = Field(default=None, min_length=1)
    tipo_resposta: str | None = Field(default=None, min_length=1, max_length=30)
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
    tipo_resposta: str


class OrdenacaoItem(BaseModel):
    pergunta_id: UUID
    ordem: int = Field(ge=0)


class OrdenacaoFormulariosRequest(BaseModel):
    itens: list[OrdenacaoItem] = Field(min_length=1)


class FormularioDetalheResponse(FormularioResponse):
    perguntas: list[FormularioPerguntaResponse] = Field(default_factory=list)
