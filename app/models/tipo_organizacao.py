from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class TipoOrganizacao(Base):
    __tablename__ = "tipos_organizacao"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    codigo = Column(String(50), nullable=False, unique=True)
    nome = Column(String(120), nullable=False)
    descricao = Column(Text, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    ordem = Column(Integer, nullable=False)
    padrao_sistema = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class EmpresaTipoOrganizacao(Base):
    __tablename__ = "empresas_tipos_organizacao"

    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id", ondelete="CASCADE"), primary_key=True)
    tipo_organizacao_id = Column(UUID(as_uuid=True), ForeignKey("tipos_organizacao.id", ondelete="RESTRICT"), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
