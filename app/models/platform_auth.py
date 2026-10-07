from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.database import Base


class PlatformUsuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    nome = Column(String(150), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    is_superadmin = Column(Boolean, nullable=False, default=False)
    ativo = Column(Boolean, nullable=False, default=True)
    ultimo_login_em = Column(DateTime(timezone=True), nullable=True)
    mfa_habilitado = Column(Boolean, nullable=False, default=False)
    mfa_secret_enc = Column(Text, nullable=True)
    mfa_confirmado_em = Column(DateTime(timezone=True), nullable=True)
    # Migration platform 010: excecao controlada de MFA (App Review da Meta) e validade de acesso.
    mfa_dispensado = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    acesso_expira_em = Column(DateTime(timezone=True), nullable=True)
    senha_alterada_em = Column(DateTime(timezone=True), nullable=True)
    tentativas_login = Column(Integer, nullable=False, default=0)
    bloqueado_ate = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlatformTenant(Base):
    __tablename__ = "tenants"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True)
    codigo = Column(String(50), nullable=False, unique=True)
    nome = Column(String(150), nullable=False)
    slug = Column(String(100), nullable=False, unique=True)
    ativo = Column(Boolean, nullable=False, default=True)
    tenant_sistema = Column(Boolean, nullable=False, default=False)


class PlatformUsuarioTenant(Base):
    __tablename__ = "usuarios_tenants"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)


class PlatformSessaoUsuario(Base):
    __tablename__ = "sessoes_usuario"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    refresh_token_hash = Column(Text, nullable=False)
    criada_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expira_em = Column(DateTime(timezone=True), nullable=False)
    ultimo_uso_em = Column(DateTime(timezone=True), nullable=True)
    revogada_em = Column(DateTime(timezone=True), nullable=True)
    motivo_revogacao = Column(Text, nullable=True)
    ip_origem = Column(String(100), nullable=True)
    user_agent = Column(Text, nullable=True)
    contexto_tipo = Column(String(20), nullable=True)  # NULL = sessao legada
    tenant_id = Column(UUID(as_uuid=True), nullable=True)
    empresa_id = Column(UUID(as_uuid=True), nullable=True)

class PlatformTipoEndpoint(Base):
    __tablename__ = "tipos_endpoint"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    codigo = Column(String(50), nullable=False, unique=True)
    nome = Column(String(100), nullable=False)
    descricao = Column(Text, nullable=True)
    ordem = Column(Integer, nullable=False, default=0)
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlatformTenantEndpoint(Base):
    __tablename__ = "tenant_endpoints"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    tipo_endpoint_id = Column(UUID(as_uuid=True), ForeignKey("tipos_endpoint.id", ondelete="RESTRICT"), nullable=False)
    codigo = Column(String(100), nullable=False)
    nome = Column(String(150), nullable=False)
    identificador_publico = Column(String(255), nullable=True)
    identificador_externo = Column(String(255), nullable=True)
    url = Column(Text, nullable=True)
    configuracao = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())



class PlatformTenantBranding(Base):
    __tablename__ = "tenant_branding"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
    admin_host = Column(String(255), nullable=True)
    nome_exibicao = Column(String(150), nullable=True)
    logo_url = Column(Text, nullable=True)
    favicon_url = Column(Text, nullable=True)
    cor_primaria = Column(String(7), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlatformTenantDatabase(Base):
    __tablename__ = "tenant_databases"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True)
    tipo_infra = Column(String(30), nullable=False, server_default=text("'MDP_SHARED'"))
    host = Column(String(255), nullable=False)
    porta = Column(Integer, nullable=False, server_default=text("5432"))
    database_name = Column(String(150), nullable=False, unique=True)
    username = Column(String(150), nullable=False)
    secret_ref = Column(Text, nullable=True)
    ativo = Column(Boolean, nullable=False, server_default=text("true"))
    versao_schema = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlatformFuncionalidade(Base):
    __tablename__ = "funcionalidades"
    id = Column(UUID(as_uuid=True), primary_key=True)
    codigo = Column(String(100), nullable=False, unique=True)
    nome = Column(String(150), nullable=False)
    descricao = Column(Text, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    ordem = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

class PlatformTenantFuncionalidade(Base):
    __tablename__ = "tenants_funcionalidades"
    id = Column(UUID(as_uuid=True), primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    funcionalidade_id = Column(UUID(as_uuid=True), ForeignKey("funcionalidades.id", ondelete="CASCADE"), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)
    habilitado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    desabilitado_em = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlatformProvedorIntegracao(Base):
    __tablename__ = "provedores_integracao"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    codigo = Column(String(50), nullable=False, unique=True)
    nome = Column(String(150), nullable=False)
    descricao = Column(Text, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

class PlatformAplicacaoIntegracao(Base):
    __tablename__ = "aplicacoes_integracao"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    provedor_id = Column(UUID(as_uuid=True), ForeignKey("provedores_integracao.id", ondelete="RESTRICT"), nullable=False)
    codigo = Column(String(100), nullable=False, unique=True)
    nome = Column(String(150), nullable=False)
    app_id = Column(String(255), nullable=True)
    owner_business_id = Column(String(255), nullable=True)
    embedded_signup_config_id = Column(String(255), nullable=True)
    graph_api_version = Column(String(50), nullable=True)
    modo = Column(String(30), nullable=True)
    status_revisao = Column(String(50), nullable=True)
    callback_url = Column(Text, nullable=True)
    permissoes = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    webhook_campos = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    app_secret_ref = Column(Text, nullable=True)
    access_token_ref = Column(Text, nullable=True)
    verify_token_ref = Column(Text, nullable=True)
    observacoes = Column(Text, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
