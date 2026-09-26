from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TipoOrganizacaoCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=50)
    nome: str = Field(min_length=1, max_length=120)
    descricao: str | None = None
    ordem: int | None = Field(default=None, ge=1)
    ativo: bool = True

    @field_validator("codigo")
    @classmethod
    def normalizar_codigo(cls, value: str):
        return value.strip().upper().replace(" ", "_")


class TipoOrganizacaoUpdate(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=50)
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    descricao: str | None = None
    ordem: int | None = Field(default=None, ge=1)
    ativo: bool | None = None

    @field_validator("codigo")
    @classmethod
    def normalizar_codigo(cls, value: str | None):
        return value.strip().upper().replace(" ", "_") if value is not None else None


class TipoOrganizacaoResponse(BaseModel):
    id: UUID
    codigo: str
    nome: str
    descricao: str | None
    ativo: bool
    ordem: int
    padrao_sistema: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class TiposEmpresaUpdate(BaseModel):
    tipo_ids: list[UUID] = Field(default_factory=list)
