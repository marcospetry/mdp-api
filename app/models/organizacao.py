from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class TipoUnidade(Base):
    __tablename__ = "tipos_unidade"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id", ondelete="CASCADE"), nullable=True)
    codigo = Column(String(50), nullable=False)
    nome = Column(String(120), nullable=False)
    descricao = Column(Text, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    ordem = Column(Integer, nullable=False)
    padrao_sistema = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class UnidadeEmpresa(Base):
    __tablename__ = "unidades_empresa"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo", name="unidades_empresa_codigo_key"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False)
    tipo_unidade_id = Column(UUID(as_uuid=True), ForeignKey("tipos_unidade.id", ondelete="RESTRICT"), nullable=False)
    codigo = Column(String(50), nullable=False)
    nome = Column(String(150), nullable=False)
    nome_fantasia = Column(String(150), nullable=True)
    cnpj = Column(String(20), nullable=True)
    email = Column(String(150), nullable=True)
    telefone = Column(String(30), nullable=True)
    cep = Column(String(10), nullable=True)
    logradouro = Column(String(180), nullable=True)
    numero = Column(String(30), nullable=True)
    complemento = Column(String(100), nullable=True)
    bairro = Column(String(100), nullable=True)
    cidade = Column(String(120), nullable=True)
    uf = Column(String(2), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    tipo_unidade = relationship("TipoUnidade")


class Area(Base):
    __tablename__ = "areas"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False)
    unidade_id = Column(UUID(as_uuid=True), ForeignKey("unidades_empresa.id", ondelete="CASCADE"), nullable=True)
    codigo = Column(String(50), nullable=False)
    nome = Column(String(150), nullable=False)
    descricao = Column(Text, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    ordem = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    unidade = relationship("UnidadeEmpresa")


class UsuarioUnidade(Base):
    __tablename__ = "usuarios_unidades"
    __table_args__ = (UniqueConstraint("usuario_empresa_id", "unidade_id", name="usuarios_unidades_vinculo_key"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    usuario_empresa_id = Column(UUID(as_uuid=True), ForeignKey("usuarios_empresas.id", ondelete="CASCADE"), nullable=False)
    unidade_id = Column(UUID(as_uuid=True), ForeignKey("unidades_empresa.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class UsuarioArea(Base):
    __tablename__ = "usuarios_areas"
    __table_args__ = (UniqueConstraint("usuario_empresa_id", "area_id", name="usuarios_areas_vinculo_key"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    usuario_empresa_id = Column(UUID(as_uuid=True), ForeignKey("usuarios_empresas.id", ondelete="CASCADE"), nullable=False)
    area_id = Column(UUID(as_uuid=True), ForeignKey("areas.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
