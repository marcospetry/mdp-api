from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
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
