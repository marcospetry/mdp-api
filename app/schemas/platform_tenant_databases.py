from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class TenantDatabaseCreate(BaseModel):
    tipo_infra: str = Field(default="MDP_SHARED", min_length=1, max_length=30)
    host: str = Field(min_length=1, max_length=255)
    porta: int = Field(default=5432, ge=1, le=65535)
    database_name: str = Field(min_length=1, max_length=150, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    username: str = Field(min_length=1, max_length=150)
    secret_ref: str | None = Field(default=None, max_length=1000)
    ativo: bool = True
    versao_schema: str | None = Field(default=None, max_length=50)


class TenantDatabaseUpdate(BaseModel):
    tipo_infra: str | None = Field(default=None, min_length=1, max_length=30)
    host: str | None = Field(default=None, min_length=1, max_length=255)
    porta: int | None = Field(default=None, ge=1, le=65535)
    database_name: str | None = Field(default=None, min_length=1, max_length=150, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    username: str | None = Field(default=None, min_length=1, max_length=150)
    secret_ref: str | None = Field(default=None, max_length=1000)
    ativo: bool | None = None
    versao_schema: str | None = Field(default=None, max_length=50)


class TenantDatabaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    tipo_infra: str
    host: str
    porta: int
    database_name: str
    username: str
    ativo: bool
    versao_schema: str | None
    # secret_ref deliberadamente nao retornado pela API.
