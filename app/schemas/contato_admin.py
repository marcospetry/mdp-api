from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


ContatoStatus = Literal["NOVO", "EM_ANALISE", "QUALIFICADO", "DESCARTADO"]


class ContatoAdminCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    empresa_id: UUID | None = None
    email: EmailStr | None = None
    telefone: str | None = Field(default=None, max_length=30)
    empresa_contato: str | None = Field(default=None, max_length=150)
    mensagem: str | None = None
    origem_contato_id: UUID | None = None
    origem: str = Field(default="ADMIN", max_length=50)
    status: ContatoStatus = "NOVO"
    tipo_solicitacao: Literal["CONTATO", "DIAGNOSTICO"] = "CONTATO"
    cnpj: str | None = Field(default=None, max_length=20)
    cidade: str | None = Field(default=None, max_length=120)
    uf: str | None = Field(default=None, max_length=2)
    site_instagram: str | None = Field(default=None, max_length=255)
    segmento: str | None = Field(default=None, max_length=150)
    objetivos: list[str] = Field(default_factory=list)

    @field_validator("nome")
    @classmethod
    def normalizar_nome(cls, value: str):
        return value.strip()

    @field_validator("uf")
    @classmethod
    def normalizar_uf(cls, value: str | None):
        if value is None:
            return None
        value = value.strip().upper()
        if value and len(value) != 2:
            raise ValueError("UF deve possuir 2 caracteres.")
        return value or None


class ContatoAdminUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    email: EmailStr | None = None
    telefone: str | None = Field(default=None, max_length=30)
    empresa_contato: str | None = Field(default=None, max_length=150)
    mensagem: str | None = None
    origem_contato_id: UUID | None = None
    origem: str | None = Field(default=None, max_length=50)
    status: ContatoStatus | None = None
    tipo_solicitacao: Literal["CONTATO", "DIAGNOSTICO"] | None = None
    cnpj: str | None = Field(default=None, max_length=20)
    cidade: str | None = Field(default=None, max_length=120)
    uf: str | None = Field(default=None, max_length=2)
    site_instagram: str | None = Field(default=None, max_length=255)
    segmento: str | None = Field(default=None, max_length=150)
    objetivos: list[str] | None = None

    @field_validator("nome")
    @classmethod
    def normalizar_nome(cls, value: str | None):
        return value.strip() if value is not None else None

    @field_validator("uf")
    @classmethod
    def normalizar_uf(cls, value: str | None):
        if value is None:
            return None
        value = value.strip().upper()
        if value and len(value) != 2:
            raise ValueError("UF deve possuir 2 caracteres.")
        return value or None


class ContatoAdminResponse(BaseModel):
    id: UUID
    empresa_id: UUID
    empresa_nome: str | None = None
    nome: str
    email: EmailStr | None
    telefone: str | None
    empresa_contato: str | None
    mensagem: str | None
    origem_contato_id: UUID | None
    origem_contato_nome: str | None = None
    origem: str
    origem_primeiro_contato: str | None
    origem_ultimo_contato: str | None
    status: str
    tipo_solicitacao: str
    cnpj: str | None
    cidade: str | None
    uf: str | None
    site_instagram: str | None
    segmento: str | None
    objetivos: list[str] | None
    consentimento_dados: bool
    consentimento_em: datetime | None
    consentimento_versao: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VincularEmpresaRequest(BaseModel):
    empresa_id: UUID


class CriarEmpresaDoContatoRequest(BaseModel):
    nome: str | None = Field(default=None, max_length=150)
    slug: str | None = Field(default=None, max_length=80)
    cnpj: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    telefone: str | None = Field(default=None, max_length=30)
    dominio: str | None = Field(default=None, max_length=255)
    status: Literal["EM_AVALIACAO", "CLIENTE", "DESCARTADA"] = "EM_AVALIACAO"
