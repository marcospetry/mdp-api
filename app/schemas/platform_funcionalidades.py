from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class FuncionalidadeCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=100)
    nome: str = Field(min_length=1, max_length=150)
    descricao: str | None = None
    ativo: bool = True
    ordem: int = 0

class FuncionalidadeUpdate(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=100)
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    descricao: str | None = None
    ativo: bool | None = None
    ordem: int | None = None

class FuncionalidadeResponse(FuncionalidadeCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID

class HabilitacaoUpdate(BaseModel):
    ativo: bool

class HabilitacaoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    funcionalidade_id: UUID
    ativo: bool
