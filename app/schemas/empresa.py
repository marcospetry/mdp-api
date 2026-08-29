from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


EmpresaStatus = Literal["EM_AVALIACAO", "CLIENTE", "DESCARTADA"]


class EmpresaCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    slug: str | None = Field(default=None, max_length=80)
    cnpj: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    telefone: str | None = Field(default=None, max_length=30)
    dominio: str | None = Field(default=None, max_length=255)
    status: EmpresaStatus = "EM_AVALIACAO"
    ativo: bool = True

    @field_validator("nome")
    @classmethod
    def normalizar_nome(cls, value: str):
        return value.strip()

    @field_validator("slug", "cnpj", "telefone", "dominio")
    @classmethod
    def limpar_texto_opcional(cls, value: str | None):
        if value is None:
            return None
        value = value.strip()
        return value or None


class EmpresaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    slug: str | None = Field(default=None, max_length=80)
    cnpj: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    telefone: str | None = Field(default=None, max_length=30)
    dominio: str | None = Field(default=None, max_length=255)
    status: EmpresaStatus | None = None
    ativo: bool | None = None

    @field_validator("nome")
    @classmethod
    def normalizar_nome(cls, value: str | None):
        if value is None:
            return None
        return value.strip()

    @field_validator("slug", "cnpj", "telefone", "dominio")
    @classmethod
    def limpar_texto_opcional(cls, value: str | None):
        if value is None:
            return None
        value = value.strip()
        return value or None


class EmpresaResponse(BaseModel):
    id: UUID
    nome: str
    slug: str
    cnpj: str | None
    email: EmailStr | None
    telefone: str | None
    dominio: str | None
    status: str
    ativo: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EmpresaDetalheResponse(EmpresaResponse):
    total_contatos: int = 0
