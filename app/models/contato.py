import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
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
