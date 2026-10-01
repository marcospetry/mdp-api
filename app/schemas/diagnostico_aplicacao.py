from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AplicacaoDiagnosticoCreate(BaseModel):
    contato_id: UUID
    formulario_id: UUID


class AplicacaoAcessoCreate(BaseModel):
    dias_validade: int = Field(default=7, ge=1, le=30)


class AplicacaoAcessoGeradoResponse(BaseModel):
    aplicacao_id: UUID
    token: str
    caminho_publico: str
    token_expira_em: datetime


class AplicacaoDiagnosticoResponse(BaseModel):
    id: UUID
    empresa_id: UUID
    contato_id: UUID | None
    contato_nome: str | None
    formulario_id: UUID | None
    formulario_nome: str | None
    formulario_codigo: str | None
    formulario_versao: int | None
    status: str
    iniciado_em: datetime
    concluido_em: datetime | None
    created_at: datetime
    acesso_gerado: bool = False
    token_expira_em: datetime | None = None
    token_revogado_em: datetime | None = None
    acesso_expirado: bool = False
