from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class UsuarioTenantLocal(Base):
    __tablename__ = "usuarios_tenant"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    platform_usuario_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Perfil(Base):
    __tablename__ = "perfis"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    codigo = Column(String(40), nullable=False, unique=True)
    nome = Column(String(80), nullable=False)
    descricao = Column(Text, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    acesso_total = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class UsuarioEmpresa(Base):
    __tablename__ = "usuarios_empresas"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios_tenant.id", ondelete="CASCADE"), nullable=False)
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False)
    perfil_id = Column(UUID(as_uuid=True), ForeignKey("perfis.id"), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)
    acesso_todas_unidades = Column(Boolean, nullable=False, default=False)
    acesso_todas_areas = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    perfil = relationship("Perfil")


class Permissao(Base):
    __tablename__ = "permissoes"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    codigo = Column(String(100), nullable=False, unique=True)
    nome = Column(String(150), nullable=False)
    descricao = Column(Text, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PerfilPermissao(Base):
    __tablename__ = "perfis_permissoes"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    perfil_id = Column(UUID(as_uuid=True), ForeignKey("perfis.id", ondelete="CASCADE"), nullable=False)
    permissao_id = Column(UUID(as_uuid=True), ForeignKey("permissoes.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    permissao = relationship("Permissao")
