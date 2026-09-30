from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TenantCreate(BaseModel):
    codigo: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    nome: str = Field(min_length=1, max_length=150)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    ativo: bool = True


class TenantUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    slug: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    ativo: bool | None = None


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    codigo: str
    nome: str
    slug: str
    ativo: bool
    tenant_sistema: bool
