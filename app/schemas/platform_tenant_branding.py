from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

HOST_PATTERN = r"^[A-Za-z0-9.-]+$"
COLOR_PATTERN = r"^#[0-9A-Fa-f]{6}$"

class TenantBrandingCreate(BaseModel):
    admin_host: str | None = Field(default=None, max_length=255, pattern=HOST_PATTERN)
    nome_exibicao: str | None = Field(default=None, max_length=150)
    logo_url: str | None = Field(default=None, max_length=2000)
    favicon_url: str | None = Field(default=None, max_length=2000)
    cor_primaria: str | None = Field(default=None, pattern=COLOR_PATTERN)
    ativo: bool = True

class TenantBrandingUpdate(BaseModel):
    admin_host: str | None = Field(default=None, max_length=255, pattern=HOST_PATTERN)
    nome_exibicao: str | None = Field(default=None, max_length=150)
    logo_url: str | None = Field(default=None, max_length=2000)
    favicon_url: str | None = Field(default=None, max_length=2000)
    cor_primaria: str | None = Field(default=None, pattern=COLOR_PATTERN)
    ativo: bool | None = None

class TenantBrandingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    admin_host: str | None
    nome_exibicao: str | None
    logo_url: str | None
    favicon_url: str | None
    cor_primaria: str | None
    ativo: bool
