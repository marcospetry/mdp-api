import uuid

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class Interacao(Base):
    """Interação relevante de um contato já aceito na base MDP.

    O Chatwoot continua sendo a caixa operacional e pode conter mensagens
    não qualificadas (spam, testes, trotes etc.). Esta tabela não é uma
    réplica integral do Chatwoot.
    """

    __tablename__ = "interacoes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    empresa_id = Column(
        UUID(as_uuid=True),
        ForeignKey("empresas.id"),
        nullable=False,
    )

    contato_id = Column(
        UUID(as_uuid=True),
        ForeignKey("contatos.id", ondelete="CASCADE"),
        nullable=False,
    )

    canal = Column(String(30), nullable=False)
    origem = Column(String(50), nullable=True)
    tipo_interacao = Column(String(30), nullable=False, default="MENSAGEM")
    mensagem = Column(Text, nullable=True)
    direcao = Column(String(15), nullable=True)
    classificacao = Column(String(30), nullable=True)

    chatwoot_conversation_id = Column(BigInteger, nullable=True)
    chatwoot_message_id = Column(BigInteger, nullable=True)
    chatwoot_inbox_id = Column(BigInteger, nullable=True)

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
