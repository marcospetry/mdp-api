from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class ContatoCreate(BaseModel):
    nome: str
    email: EmailStr
    telefone: str | None = None
    empresa_contato: str | None = None
    mensagem: str


class ContatoResponse(BaseModel):
    id: UUID
    empresa_id: UUID
    nome: str
    email: EmailStr
    telefone: str | None
    empresa_contato: str | None
    mensagem: str
    origem: str
    status: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
