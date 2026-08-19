from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1, max_length=512)
    empresa_id: UUID | None = None


class LoginResponse(BaseModel):
    status: str
    preauth_token: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MFAVerifyRequest(BaseModel):
    preauth_token: str
    codigo: str = Field(pattern=r"^\d{6}$")


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class EmpresaAcesso(BaseModel):
    empresa_id: UUID
    perfil: str


class MeResponse(BaseModel):
    id: UUID
    nome: str
    email: EmailStr
    is_superadmin: bool
    empresa_id: UUID | None
    perfil: str | None
    permissoes: list[str]
