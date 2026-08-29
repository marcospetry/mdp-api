BEGIN;

-- MDP 004 - Estrutura organizacional multitenant
-- Motivo: permitir que cada empresa (tenant) possua unidades e áreas opcionais,
-- além de restringir usuários por escopo organizacional sem alterar o login atual.

CREATE TABLE IF NOT EXISTS tipos_unidade (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NULL REFERENCES empresas(id) ON DELETE CASCADE,
    codigo VARCHAR(50) NOT NULL,
    nome VARCHAR(120) NOT NULL,
    descricao TEXT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    ordem INTEGER NOT NULL,
    padrao_sistema BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT tipos_unidade_ordem_check CHECK (ordem > 0),
    CONSTRAINT tipos_unidade_padrao_check CHECK (NOT padrao_sistema OR empresa_id IS NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_tipos_unidade_codigo_global
    ON tipos_unidade (codigo) WHERE empresa_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_tipos_unidade_codigo_empresa
    ON tipos_unidade (empresa_id, codigo) WHERE empresa_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_tipos_unidade_empresa_ativo_ordem
    ON tipos_unidade (empresa_id, ativo, ordem);

INSERT INTO tipos_unidade (empresa_id, codigo, nome, descricao, ativo, ordem, padrao_sistema)
VALUES
(NULL, 'MATRIZ', 'Matriz', NULL, TRUE, 1, TRUE),
(NULL, 'FILIAL', 'Filial', NULL, TRUE, 2, TRUE),
(NULL, 'ESCRITORIO', 'Escritório', NULL, TRUE, 3, TRUE),
(NULL, 'LOJA', 'Loja', NULL, TRUE, 4, TRUE),
(NULL, 'QUIOSQUE', 'Quiosque', NULL, TRUE, 5, TRUE),
(NULL, 'FABRICA', 'Fábrica', NULL, TRUE, 6, TRUE),
(NULL, 'DISTRIBUIDORA', 'Distribuidora', NULL, TRUE, 7, TRUE),
(NULL, 'CENTRO_DISTRIBUICAO', 'Centro de Distribuição', NULL, TRUE, 8, TRUE),
(NULL, 'DEPOSITO', 'Depósito', NULL, TRUE, 9, TRUE),
(NULL, 'POSTO_ATENDIMENTO', 'Posto de Atendimento', NULL, TRUE, 10, TRUE),
(NULL, 'HOME_OFFICE', 'Home Office', NULL, TRUE, 11, TRUE),
(NULL, 'OUTRO', 'Outro', NULL, TRUE, 12, TRUE)
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS unidades_empresa (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    tipo_unidade_id UUID NOT NULL REFERENCES tipos_unidade(id) ON DELETE RESTRICT,
    codigo VARCHAR(50) NOT NULL,
    nome VARCHAR(150) NOT NULL,
    nome_fantasia VARCHAR(150) NULL,
    cnpj VARCHAR(20) NULL,
    email VARCHAR(150) NULL,
    telefone VARCHAR(30) NULL,
    cep VARCHAR(10) NULL,
    logradouro VARCHAR(180) NULL,
    numero VARCHAR(30) NULL,
    complemento VARCHAR(100) NULL,
    bairro VARCHAR(100) NULL,
    cidade VARCHAR(120) NULL,
    uf VARCHAR(2) NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT unidades_empresa_codigo_key UNIQUE (empresa_id, codigo)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_unidades_empresa_cnpj_normalizado
    ON unidades_empresa ((regexp_replace(cnpj, '[^0-9]', '', 'g')))
    WHERE cnpj IS NOT NULL AND btrim(cnpj) <> '';
CREATE INDEX IF NOT EXISTS ix_unidades_empresa_empresa_ativo
    ON unidades_empresa (empresa_id, ativo);
CREATE INDEX IF NOT EXISTS ix_unidades_empresa_tipo
    ON unidades_empresa (tipo_unidade_id);
CREATE INDEX IF NOT EXISTS ix_unidades_empresa_localidade
    ON unidades_empresa (cidade, uf);

CREATE TABLE IF NOT EXISTS areas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    unidade_id UUID NULL REFERENCES unidades_empresa(id) ON DELETE CASCADE,
    codigo VARCHAR(50) NOT NULL,
    nome VARCHAR(150) NOT NULL,
    descricao TEXT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    ordem INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT areas_ordem_check CHECK (ordem > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_areas_codigo_empresa_direta
    ON areas (empresa_id, codigo) WHERE unidade_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_areas_codigo_unidade
    ON areas (unidade_id, codigo) WHERE unidade_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_areas_ordem_empresa_direta
    ON areas (empresa_id, ordem) WHERE unidade_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_areas_ordem_unidade
    ON areas (unidade_id, ordem) WHERE unidade_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_areas_empresa_ativo ON areas (empresa_id, ativo);
CREATE INDEX IF NOT EXISTS ix_areas_unidade_ativo ON areas (unidade_id, ativo);

ALTER TABLE usuarios_empresas
    ADD COLUMN IF NOT EXISTS acesso_todas_unidades BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS acesso_todas_areas BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS usuarios_unidades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_empresa_id UUID NOT NULL REFERENCES usuarios_empresas(id) ON DELETE CASCADE,
    unidade_id UUID NOT NULL REFERENCES unidades_empresa(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT usuarios_unidades_vinculo_key UNIQUE (usuario_empresa_id, unidade_id)
);
CREATE INDEX IF NOT EXISTS ix_usuarios_unidades_unidade ON usuarios_unidades (unidade_id);

CREATE TABLE IF NOT EXISTS usuarios_areas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_empresa_id UUID NOT NULL REFERENCES usuarios_empresas(id) ON DELETE CASCADE,
    area_id UUID NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT usuarios_areas_vinculo_key UNIQUE (usuario_empresa_id, area_id)
);
CREATE INDEX IF NOT EXISTS ix_usuarios_areas_area ON usuarios_areas (area_id);

COMMIT;
