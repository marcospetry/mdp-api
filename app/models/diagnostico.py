import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class CategoriaDiagnostico(Base):
    __tablename__ = "categorias_diagnostico"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=True)
    nome = Column(String(120), nullable=False)
    descricao = Column(Text, nullable=True)
    ordem = Column(Integer, nullable=False, default=0)
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class PerguntaDiagnostico(Base):
    __tablename__ = "perguntas_diagnostico"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=True)
    categoria_id = Column(
        UUID(as_uuid=True), ForeignKey("categorias_diagnostico.id"), nullable=False
    )
    pergunta = Column(Text, nullable=False)
    tipo_resposta = Column(String(30), nullable=False)
    peso = Column(Numeric, nullable=False, default=1)
    ordem = Column(Integer, nullable=False, default=0)
    obrigatoria = Column(Boolean, nullable=False, default=False)
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    codigo = Column(String(30), nullable=True)
    metodo_avaliacao = Column(String(20), nullable=False, default="cliente")
    ajuda = Column(Text, nullable=True)
    gera_achado = Column(Boolean, nullable=False, default=True)


class OpcaoPerguntaDiagnostico(Base):
    __tablename__ = "opcoes_pergunta_diagnostico"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pergunta_id = Column(
        UUID(as_uuid=True), ForeignKey("perguntas_diagnostico.id"), nullable=False
    )
    valor = Column(String(80), nullable=False)
    rotulo = Column(String(150), nullable=False)
    pontuacao = Column(Numeric, nullable=False, default=0)
    ordem = Column(Integer, nullable=False, default=0)
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class FormularioDiagnostico(Base):
    __tablename__ = "formularios_diagnostico"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "codigo",
            "versao",
            name="uq_formularios_diagnostico_empresa_codigo_versao",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=True)
    codigo = Column(String(50), nullable=False)
    nome = Column(String(150), nullable=False)
    descricao = Column(Text, nullable=True)
    tipo = Column(String(50), nullable=False)
    versao = Column(Integer, nullable=False, default=1)
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class FormularioPergunta(Base):
    __tablename__ = "formularios_perguntas"
    __table_args__ = (
        UniqueConstraint(
            "formulario_id",
            "pergunta_id",
            name="uq_formularios_perguntas",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    formulario_id = Column(
        UUID(as_uuid=True),
        ForeignKey("formularios_diagnostico.id", ondelete="CASCADE"),
        nullable=False,
    )
    pergunta_id = Column(
        UUID(as_uuid=True), ForeignKey("perguntas_diagnostico.id"), nullable=False
    )
    ordem = Column(Integer, nullable=False, default=0)
    obrigatoria = Column(Boolean, nullable=False, default=False)
    peso = Column(Numeric, nullable=False, default=1)
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
