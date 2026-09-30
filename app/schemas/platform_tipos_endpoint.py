from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class TipoEndpointCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=50)
    nome: str = Field(min_length=1, max_length=100)
    descricao: Optional[str] = None
    ordem: int = 0
    ativo: bool = True

class TipoEndpointUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1, max_length=100)
    descricao: Optional[str] = None
    ordem: Optional[int] = None
    ativo: Optional[bool] = None

class TipoEndpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    codigo: str
    nome: str
    descricao: Optional[str]
    ordem: int
    ativo: bool
