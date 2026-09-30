from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class PlatformUsuarioResumo(BaseModel):
    id: UUID
    nome: str
    email: str
    is_superadmin: bool
    ativo: bool


class PlatformUsuarioUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=150)
    email: EmailStr | None = None
    ativo: bool | None = None


class PlatformUsuarioTenantResumo(BaseModel):
    vinculo_id: UUID | None = None
    tenant_id: UUID
    tenant_codigo: str
    tenant_nome: str
    tenant_ativo: bool
    vinculo_ativo: bool


class PlatformUsuarioDetalhe(PlatformUsuarioResumo):
    tenants: list[PlatformUsuarioTenantResumo] = []


class TenantUsuarioResponse(BaseModel):
    vinculo_id: UUID
    usuario_id: UUID
    nome: str
    email: str
    is_superadmin: bool
    usuario_ativo: bool
    vinculo_ativo: bool


class TenantUsuarioVinculoCreate(BaseModel):
    usuario_id: UUID


class TenantUsuarioVinculoUpdate(BaseModel):
    ativo: bool
