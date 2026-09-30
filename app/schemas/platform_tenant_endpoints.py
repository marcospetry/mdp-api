from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field

class EndpointCreate(BaseModel):
    tipo_endpoint_id: UUID
    codigo: str = Field(min_length=1, max_length=100)
    nome: str = Field(min_length=1, max_length=150)
    identificador_publico: Optional[str] = Field(default=None, max_length=255)
    identificador_externo: Optional[str] = Field(default=None, max_length=255)
    url: Optional[str] = None
    ativo: bool = True

class EndpointUpdate(BaseModel):
    tipo_endpoint_id: Optional[UUID] = None
    codigo: Optional[str] = Field(default=None, min_length=1, max_length=100)
    nome: Optional[str] = Field(default=None, min_length=1, max_length=150)
    identificador_publico: Optional[str] = Field(default=None, max_length=255)
    identificador_externo: Optional[str] = Field(default=None, max_length=255)
    url: Optional[str] = None
    ativo: Optional[bool] = None

class EndpointResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    tipo_endpoint_id: UUID
    tipo: str
    tipo_nome: str
    codigo: str
    nome: str
    identificador_publico: Optional[str]
    identificador_externo: Optional[str]
    url: Optional[str]
    ativo: bool
