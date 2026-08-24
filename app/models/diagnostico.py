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
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PerguntaDiagnostico(Base):
    __tablename__ = "perguntas_diagnostico"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=True)
    categoria_id = Column(UUID(as_uuid=True), ForeignKey("categorias_diagnostico.id"), nullable=False)
    pergunta = Column(Text, nullable=False)
    tipo_resposta = Column(String(30), nullable=False)
    natureza = Column(String(20), nullable=False, default="CONTEXTO")
    ideal = Column(Text, nullable=True)
    sugestao = Column(Text, nullable=True)

    # Campos legados mantidos por compatibilidade com a API/banco anteriores.
    peso = Column(Numeric, nullable=False, default=1)
    ordem = Column(Integer, nullable=False, default=0)
    obrigatoria = Column(Boolean, nullable=False, default=False)
    ativo = Column(Boolean, nullable=False, default=True)
    codigo = Column(String(30), nullable=True)
    metodo_avaliacao = Column(String(20), nullable=False, default="cliente")
    ajuda = Column(Text, nullable=True)
    gera_achado = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class OpcaoPerguntaDiagnostico(Base):
    __tablename__ = "opcoes_pergunta_diagnostico"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pergunta_id = Column(UUID(as_uuid=True), ForeignKey("perguntas_diagnostico.id", ondelete="CASCADE"), nullable=False)
    valor = Column(String(80), nullable=False)
    rotulo = Column(String(150), nullable=False)
    estado_interno = Column(String(20), nullable=True)

    # Legado mantido por compatibilidade; não comanda o novo motor.
    pontuacao = Column(Numeric, nullable=False, default=0)

    ordem = Column(Integer, nullable=False, default=0)
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class FaixaAvaliacaoNumero(Base):
    __tablename__ = "faixas_avaliacao_numero"
    __table_args__ = (
        UniqueConstraint("pergunta_id", "estado_interno", name="uq_faixas_avaliacao_numero_pergunta_estado"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pergunta_id = Column(UUID(as_uuid=True), ForeignKey("perguntas_diagnostico.id", ondelete="CASCADE"), nullable=False)
    valor_min = Column(Numeric(15, 4), nullable=True)
    valor_max = Column(Numeric(15, 4), nullable=True)
    estado_interno = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class FormularioDiagnostico(Base):
    __tablename__ = "formularios_diagnostico"
    __table_args__ = (
        UniqueConstraint("empresa_id", "codigo", "versao", name="uq_formularios_diagnostico_empresa_codigo_versao"),
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
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class FormularioPergunta(Base):
    __tablename__ = "formularios_perguntas"
    __table_args__ = (
        UniqueConstraint("formulario_id", "pergunta_id", name="uq_formularios_perguntas"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    formulario_id = Column(UUID(as_uuid=True), ForeignKey("formularios_diagnostico.id", ondelete="CASCADE"), nullable=False)
    pergunta_id = Column(UUID(as_uuid=True), ForeignKey("perguntas_diagnostico.id"), nullable=False)
    ordem = Column(Integer, nullable=False, default=0)
    obrigatoria = Column(Boolean, nullable=False, default=False)
    peso = Column(Numeric, nullable=False, default=1)
    ativo = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class RegraExibicaoPergunta(Base):
    __tablename__ = "regras_exibicao_perguntas"
    __table_args__ = (
        UniqueConstraint(
            "formulario_id",
            "pergunta_origem_id",
            "opcao_origem_id",
            "pergunta_destino_id",
            name="uq_regras_exibicao_perguntas",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    formulario_id = Column(UUID(as_uuid=True), ForeignKey("formularios_diagnostico.id", ondelete="CASCADE"), nullable=False)
    pergunta_origem_id = Column(UUID(as_uuid=True), ForeignKey("perguntas_diagnostico.id", ondelete="CASCADE"), nullable=False)
    opcao_origem_id = Column(UUID(as_uuid=True), ForeignKey("opcoes_pergunta_diagnostico.id", ondelete="CASCADE"), nullable=False)
    pergunta_destino_id = Column(UUID(as_uuid=True), ForeignKey("perguntas_diagnostico.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


# Modelos das tabelas de execução já existentes/adequadas no banco.
# A v0.5.0 ainda não publica endpoints de execução pública, mas manter os
# modelos alinhados ao schema evita novo desalinhamento entre API e banco.
class Diagnostico(Base):
    __tablename__ = "diagnosticos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=False)
    nome_contato = Column(String(150), nullable=True)
    email_contato = Column(String(150), nullable=True)
    telefone_contato = Column(String(30), nullable=True)
    empresa_avaliada = Column(String(150), nullable=True)
    status = Column(String(30), nullable=False, default="em_andamento")
    pontuacao_total = Column(Numeric(10, 2), nullable=True)
    classificacao = Column(String(50), nullable=True)
    iniciado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    concluido_em = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    contato_id = Column(UUID(as_uuid=True), ForeignKey("contatos.id"), nullable=True)
    formulario_id = Column(UUID(as_uuid=True), ForeignKey("formularios_diagnostico.id"), nullable=True)


class RespostaDiagnostico(Base):
    __tablename__ = "respostas_diagnostico"
    __table_args__ = (
        UniqueConstraint("diagnostico_id", "pergunta_id", name="respostas_diagnostico_diagnostico_id_pergunta_id_key"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    diagnostico_id = Column(UUID(as_uuid=True), ForeignKey("diagnosticos.id", ondelete="CASCADE"), nullable=False)
    pergunta_id = Column(UUID(as_uuid=True), ForeignKey("perguntas_diagnostico.id"), nullable=False)
    opcao_id = Column(UUID(as_uuid=True), ForeignKey("opcoes_pergunta_diagnostico.id"), nullable=True)
    estado_interno = Column(String(20), nullable=True)
    resposta_texto = Column(Text, nullable=True)
    resposta_numero = Column(Numeric(15, 4), nullable=True)
    resposta_boolean = Column(Boolean, nullable=True)
    pontuacao = Column(Numeric(10, 2), nullable=True)
    observacao = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class RespostaDiagnosticoOpcao(Base):
    __tablename__ = "respostas_diagnostico_opcoes"

    resposta_id = Column(UUID(as_uuid=True), ForeignKey("respostas_diagnostico.id", ondelete="CASCADE"), primary_key=True)
    opcao_id = Column(UUID(as_uuid=True), ForeignKey("opcoes_pergunta_diagnostico.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class EvidenciaDiagnostico(Base):
    __tablename__ = "evidencias_diagnostico"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    empresa_id = Column(UUID(as_uuid=True), ForeignKey("empresas.id"), nullable=False)
    diagnostico_id = Column(UUID(as_uuid=True), ForeignKey("diagnosticos.id", ondelete="CASCADE"), nullable=False)
    resposta_id = Column(UUID(as_uuid=True), ForeignKey("respostas_diagnostico.id"), nullable=True)
    tipo = Column(String(50), nullable=False)
    arquivo_url = Column(Text, nullable=True)
    descricao = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
