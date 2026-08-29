from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

class CatalogoCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=50)
    nome: str = Field(min_length=1, max_length=120)
    descricao: str | None = None
    ordem: int | None = Field(default=None, ge=1)

class CatalogoUpdate(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=50)
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    descricao: str | None = None
    ordem: int | None = Field(default=None, ge=1)

class CatalogoStatus(BaseModel):
    ativo: bool

class CatalogoResponse(BaseModel):
    id: UUID
    empresa_id: UUID | None
    codigo: str
    nome: str
    descricao: str | None
    ativo: bool
    ordem: int
    padrao_sistema: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}
