from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
    )

    nome = Column(String(150), nullable=False)
    slug = Column(String(80), nullable=False, unique=True)
    cnpj = Column(String(20), nullable=True)
    email = Column(String(150), nullable=True)
    telefone = Column(String(30), nullable=True)
    dominio = Column(String(255), nullable=True)

    ativo = Column(
        Boolean,
        nullable=False,
        default=True,
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
