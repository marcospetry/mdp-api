import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.sql import func

from app.database import Base
from app.models.empresa import Empresa


class Contato(Base):
    __tablename__ = "contatos"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    empresa_id = Column(
        UUID(as_uuid=True),
        ForeignKey("empresas.id"),
        nullable=False,
    )

    nome = Column(String(150), nullable=False)
    email = Column(String(150), nullable=False)
    telefone = Column(String(30), nullable=True)
    empresa_contato = Column(String(150), nullable=True)
    mensagem = Column(Text, nullable=False)

    origem = Column(
        String(50),
        nullable=False,
        default="site",
    )

    status = Column(
        String(30),
        nullable=False,
        default="novo",
    )

    tipo_solicitacao = Column(
        String(30),
        nullable=False,
        default="CONTATO",
    )

    cnpj = Column(String(20), nullable=True)
    cidade = Column(String(120), nullable=True)
    uf = Column(String(2), nullable=True)
    site_instagram = Column(String(255), nullable=True)
    segmento = Column(String(150), nullable=True)

    objetivos = Column(
        ARRAY(Text),
        nullable=True,
    )

    consentimento_dados = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    consentimento_em = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    consentimento_versao = Column(
        String(30),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
