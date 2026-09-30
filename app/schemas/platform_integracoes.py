from uuid import UUID
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class ProvedorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    codigo: str
    nome: str
    descricao: Optional[str]
    ativo: bool

class AplicacaoCreate(BaseModel):
    provedor_id: UUID
    codigo: str = Field(min_length=1,max_length=100)
    nome: str = Field(min_length=1,max_length=150)
    app_id: Optional[str] = Field(default=None,max_length=255)
    owner_business_id: Optional[str] = Field(default=None,max_length=255)
    embedded_signup_config_id: Optional[str] = Field(default=None,max_length=255)
    graph_api_version: Optional[str] = Field(default=None,max_length=50)
    modo: Optional[str] = Field(default=None,max_length=30)
    status_revisao: Optional[str] = Field(default=None,max_length=50)
    callback_url: Optional[str] = None
    permissoes: list[str] = []
    webhook_campos: list[str] = []
    app_secret_ref: Optional[str] = None
    access_token_ref: Optional[str] = None
    verify_token_ref: Optional[str] = None
    observacoes: Optional[str] = None
    ativo: bool = True

class AplicacaoUpdate(BaseModel):
    nome: Optional[str] = Field(default=None,min_length=1,max_length=150)
    app_id: Optional[str] = Field(default=None,max_length=255)
    owner_business_id: Optional[str] = Field(default=None,max_length=255)
    embedded_signup_config_id: Optional[str] = Field(default=None,max_length=255)
    graph_api_version: Optional[str] = Field(default=None,max_length=50)
    modo: Optional[str] = Field(default=None,max_length=30)
    status_revisao: Optional[str] = Field(default=None,max_length=50)
    callback_url: Optional[str] = None
    permissoes: Optional[list[str]] = None
    webhook_campos: Optional[list[str]] = None
    app_secret_ref: Optional[str] = None
    access_token_ref: Optional[str] = None
    verify_token_ref: Optional[str] = None
    observacoes: Optional[str] = None
    ativo: Optional[bool] = None

class AplicacaoResponse(BaseModel):
    id: UUID
    provedor_id: UUID
    provedor_codigo: str
    provedor_nome: str
    codigo: str
    nome: str
    app_id: Optional[str]
    owner_business_id: Optional[str]
    embedded_signup_config_id: Optional[str]
    graph_api_version: Optional[str]
    modo: Optional[str]
    status_revisao: Optional[str]
    callback_url: Optional[str]
    permissoes: list[str]
    webhook_campos: list[str]
    observacoes: Optional[str]
    ativo: bool
    has_app_secret: bool
    has_access_token: bool
    has_verify_token: bool
