from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class _TextoMixin(BaseModel):
    @field_validator("codigo", check_fields=False)
    @classmethod
    def normalizar_codigo(cls, value: str):
        return value.strip().upper().replace(" ", "_")


class TipoUnidadeCreate(_TextoMixin):
    codigo: str = Field(min_length=2, max_length=50)
    nome: str = Field(min_length=2, max_length=120)
    descricao: str | None = None
    ordem: int = Field(ge=1)
    ativo: bool = True


class TipoUnidadeUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=120)
    descricao: str | None = None
    ordem: int | None = Field(default=None, ge=1)
    ativo: bool | None = None


class TipoUnidadeResponse(BaseModel):
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


class StatusUpdate(BaseModel):
    ativo: bool


class UnidadeCreate(_TextoMixin):
    tipo_unidade_id: UUID
    codigo: str = Field(min_length=1, max_length=50)
    nome: str = Field(min_length=2, max_length=150)
    nome_fantasia: str | None = Field(default=None, max_length=150)
    cnpj: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    telefone: str | None = Field(default=None, max_length=30)
    cep: str | None = Field(default=None, max_length=10)
    logradouro: str | None = Field(default=None, max_length=180)
    numero: str | None = Field(default=None, max_length=30)
    complemento: str | None = Field(default=None, max_length=100)
    bairro: str | None = Field(default=None, max_length=100)
    cidade: str | None = Field(default=None, max_length=120)
    uf: str | None = Field(default=None, min_length=2, max_length=2)
    ativo: bool = True


class UnidadeUpdate(BaseModel):
    tipo_unidade_id: UUID | None = None
    codigo: str | None = Field(default=None, min_length=1, max_length=50)
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    nome_fantasia: str | None = Field(default=None, max_length=150)
    cnpj: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    telefone: str | None = Field(default=None, max_length=30)
    cep: str | None = Field(default=None, max_length=10)
    logradouro: str | None = Field(default=None, max_length=180)
    numero: str | None = Field(default=None, max_length=30)
    complemento: str | None = Field(default=None, max_length=100)
    bairro: str | None = Field(default=None, max_length=100)
    cidade: str | None = Field(default=None, max_length=120)
    uf: str | None = Field(default=None, min_length=2, max_length=2)
    ativo: bool | None = None

    @field_validator("codigo")
    @classmethod
    def normalizar_codigo(cls, value):
        return value.strip().upper().replace(" ", "_") if value else value


class UnidadeResponse(BaseModel):
    id: UUID
    empresa_id: UUID
    tipo_unidade_id: UUID
    codigo: str
    nome: str
    nome_fantasia: str | None
    cnpj: str | None
    email: EmailStr | None
    telefone: str | None
    cep: str | None
    logradouro: str | None
    numero: str | None
    complemento: str | None
    bairro: str | None
    cidade: str | None
    uf: str | None
    ativo: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class AreaCreate(_TextoMixin):
    unidade_id: UUID | None = None
    codigo: str = Field(min_length=1, max_length=50)
    nome: str = Field(min_length=2, max_length=150)
    descricao: str | None = None
    ordem: int = Field(ge=1)
    ativo: bool = True


class AreaUpdate(BaseModel):
    unidade_id: UUID | None = None
    codigo: str | None = Field(default=None, min_length=1, max_length=50)
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    descricao: str | None = None
    ordem: int | None = Field(default=None, ge=1)
    ativo: bool | None = None

    @field_validator("codigo")
    @classmethod
    def normalizar_codigo(cls, value):
        return value.strip().upper().replace(" ", "_") if value else value


class AreaResponse(BaseModel):
    id: UUID
    empresa_id: UUID
    unidade_id: UUID | None
    codigo: str
    nome: str
    descricao: str | None
    ativo: bool
    ordem: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class EscopoUsuarioUpdate(BaseModel):
    acesso_todas_unidades: bool | None = None
    acesso_todas_areas: bool | None = None


class VinculoUnidadeCreate(BaseModel):
    unidade_id: UUID


class VinculoAreaCreate(BaseModel):
    area_id: UUID
