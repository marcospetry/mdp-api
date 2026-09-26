BEGIN;

ALTER TABLE empresas
    ADD COLUMN IF NOT EXISTS organizacao_principal BOOLEAN NOT NULL DEFAULT FALSE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_empresas_organizacao_principal
    ON empresas (organizacao_principal)
    WHERE organizacao_principal = TRUE;

CREATE TABLE IF NOT EXISTS tipos_organizacao (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nome VARCHAR(120) NOT NULL,
    descricao TEXT,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    ordem INTEGER NOT NULL,
    padrao_sistema BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_tipos_organizacao_ordem CHECK (ordem >= 1)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tipos_organizacao_ordem
    ON tipos_organizacao (ordem);

CREATE TABLE IF NOT EXISTS empresas_tipos_organizacao (
    empresa_id UUID NOT NULL,
    tipo_organizacao_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (empresa_id, tipo_organizacao_id),
    CONSTRAINT fk_empresas_tipos_empresa
        FOREIGN KEY (empresa_id) REFERENCES empresas(id) ON DELETE CASCADE,
    CONSTRAINT fk_empresas_tipos_tipo
        FOREIGN KEY (tipo_organizacao_id) REFERENCES tipos_organizacao(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_empresas_tipos_tipo
    ON empresas_tipos_organizacao (tipo_organizacao_id);

-- A API do tenant conecta com o papel mdp. Ao executar a migration como postgres,
-- garante que as novas tabelas continuem acessíveis pela aplicação.
ALTER TABLE tipos_organizacao OWNER TO mdp;
ALTER TABLE empresas_tipos_organizacao OWNER TO mdp;

INSERT INTO tipos_organizacao (codigo,nome,descricao,ordem,padrao_sistema,ativo)
VALUES
('CLIENTE','Cliente','Organização cliente da organização principal do Tenant.',1,TRUE,TRUE),
('FORNECEDOR','Fornecedor','Organização fornecedora de produtos ou serviços.',2,TRUE,TRUE),
('TERCEIRO','Terceiro','Organização terceira relacionada à operação.',3,TRUE,TRUE),
('ORGAO_EXTERNO','Órgão Externo','Órgão externo relacionado à operação.',4,TRUE,TRUE),
('BANCO','Banco','Instituição bancária ou financeira relacionada.',5,TRUE,TRUE),
('PARCEIRO','Parceiro','Organização parceira.',6,TRUE,TRUE)
ON CONFLICT (codigo) DO UPDATE SET
    nome=EXCLUDED.nome,
    descricao=EXCLUDED.descricao,
    padrao_sistema=TRUE;

UPDATE empresas
SET organizacao_principal = TRUE
WHERE slug = 'mdp'
  AND NOT EXISTS (
      SELECT 1 FROM empresas e2
      WHERE e2.organizacao_principal = TRUE
        AND e2.id <> empresas.id
  );

COMMIT;
