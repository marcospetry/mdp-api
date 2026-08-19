from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    nome = Column(String(150), nullable=False)
    email = Column(String(150), nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    is_superadmin = Column(Boolean, nullable=False, default=False)
    ativo = Column(Boolean, nullable=False, default=True)
    ultimo_login_em = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    mfa_habilitado = Column(Boolean, nullable=False, default=False)
    mfa_secret_enc = Column(Text, nullable=True)
    mfa_confirmado_em = Column(DateTime(timezone=True), nullable=True)
    senha_alterada_em = Column(DateTime(timezone=True), nullable=True)
    tentativas_login = Column(Integer, nullable=False, default=0)
    bloqueado_ate = Column(DateTime(timezone=True), nullable=True)


class Perfil(Base):
    __tablename__ = "perfis"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    codigo = Column(String(40), nullable=False, unique=True)
    nome = Column(String(80), nullable=False)
    descricao = Column(Text, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class UsuarioEmpresa(Base):
    __tablename__ = "usuarios_empresas"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False)
    perfil_id = Column(UUID(as_uuid=True), ForeignKey("perfis.id"), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)
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
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PerfilPermissao(Base):
    __tablename__ = "perfis_permissoes"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    perfil_id = Column(UUID(as_uuid=True), ForeignKey("perfis.id", ondelete="CASCADE"), nullable=False)
    permissao_id = Column(UUID(as_uuid=True), ForeignKey("permissoes.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    permissao = relationship("Permissao")


class SessaoUsuario(Base):
    __tablename__ = "sessoes_usuario"
    __table_args__ = (CheckConstraint("expira_em > criada_em", name="sessoes_usuario_expiracao_check"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id", ondelete="RESTRICT"), nullable=True)
    refresh_token_hash = Column(Text, nullable=False)
    criada_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expira_em = Column(DateTime(timezone=True), nullable=False)
    ultimo_uso_em = Column(DateTime(timezone=True), nullable=True)
    revogada_em = Column(DateTime(timezone=True), nullable=True)
    motivo_revogacao = Column(String(255), nullable=True)
    ip_origem = Column(INET, nullable=True)
    user_agent = Column(Text, nullable=True)
