BEGIN;

-- ============================================================
-- MDP - Migration 004
-- Catálogos pertencentes ao Tenant
--
-- No modelo multitenant atual, cada Tenant possui seu próprio
-- banco operacional. Portanto, estes catálogos são do Tenant
-- inteiro e não precisam de empresa_id:
--
--   origens_contato
--   tipos_interacao
--   tipos_unidade
-- ============================================================


-- ------------------------------------------------------------
-- 1. ORIGENS DE CONTATO
-- ------------------------------------------------------------

DROP INDEX IF EXISTS idx_origens_contato_empresa;
DROP INDEX IF EXISTS uq_origens_contato_empresa_codigo;
DROP INDEX IF EXISTS uq_origens_contato_global_codigo;

ALTER TABLE origens_contato
    DROP CONSTRAINT IF EXISTS origens_contato_empresa_id_fkey;

ALTER TABLE origens_contato
    DROP COLUMN IF EXISTS empresa_id;

CREATE UNIQUE INDEX uq_origens_contato_codigo
    ON origens_contato (upper(codigo));


-- ------------------------------------------------------------
-- 2. TIPOS DE INTERAÇÃO
-- ------------------------------------------------------------

DROP INDEX IF EXISTS idx_tipos_interacao_empresa;
DROP INDEX IF EXISTS uq_tipos_interacao_empresa_codigo;
DROP INDEX IF EXISTS uq_tipos_interacao_global_codigo;

ALTER TABLE tipos_interacao
    DROP CONSTRAINT IF EXISTS tipos_interacao_empresa_id_fkey;

ALTER TABLE tipos_interacao
    DROP COLUMN IF EXISTS empresa_id;

CREATE UNIQUE INDEX uq_tipos_interacao_codigo
    ON tipos_interacao (upper(codigo));


-- ------------------------------------------------------------
-- 3. TIPOS DE UNIDADE
-- ------------------------------------------------------------

DROP INDEX IF EXISTS ix_tipos_unidade_empresa_ativo_ordem;
DROP INDEX IF EXISTS ux_tipos_unidade_codigo_empresa;
DROP INDEX IF EXISTS ux_tipos_unidade_codigo_global;

ALTER TABLE tipos_unidade
    DROP CONSTRAINT IF EXISTS tipos_unidade_padrao_check;

ALTER TABLE tipos_unidade
    DROP CONSTRAINT IF EXISTS tipos_unidade_empresa_id_fkey;

ALTER TABLE tipos_unidade
    DROP COLUMN IF EXISTS empresa_id;

CREATE UNIQUE INDEX ux_tipos_unidade_codigo
    ON tipos_unidade (upper(codigo));

CREATE INDEX ix_tipos_unidade_ativo_ordem
    ON tipos_unidade (ativo, ordem);

-- ------------------------------------------------------------
-- 4. SEED DOS CATÁLOGOS DO TENANT
-- ------------------------------------------------------------

INSERT INTO origens_contato
    (codigo, nome, ordem, padrao_sistema)
VALUES
    ('SITE',              'Site',              1,  true),
    ('ADMIN',             'Cadastro manual',   2,  true),
    ('WHATSAPP',          'WhatsApp',           3,  true),
    ('INSTAGRAM',         'Instagram',          4,  true),
    ('EMAIL',             'E-mail',             5,  true),
    ('TELEFONE',          'Telefone',           6,  true),
    ('VISITA_PRESENCIAL', 'Visita presencial', 7,  true),
    ('INDICACAO',         'Indicação',          8,  true),
    ('GOOGLE',            'Google',             9,  true),
    ('EVENTO',            'Evento',             10, true),
    ('META_ADS',          'Meta Ads',           11, true),
    ('GOOGLE_ADS',        'Google Ads',         12, true),
    ('PARCERIA',          'Parceria',           13, true),
    ('PROSPECCAO_ATIVA',  'Prospecção ativa',  14, true),
    ('OUTRO',             'Outro',              15, true),
    ('OMNI',              'Omni',               16, true)
ON CONFLICT DO NOTHING;


INSERT INTO tipos_interacao
    (codigo, nome, ordem, padrao_sistema)
VALUES
    ('FORMULARIO_SITE',       'Formulário do site',      1,  true),
    ('WHATSAPP_MENSAGEM',     'WhatsApp - Mensagem',     2,  true),
    ('INSTAGRAM_DIRECT',      'Instagram - Direct',      3,  true),
    ('INSTAGRAM_COMENTARIO',  'Instagram - Comentário',  4,  true),
    ('EMAIL',                 'E-mail',                   5,  true),
    ('LIGACAO',               'Ligação',                  6,  true),
    ('VISITA',                'Visita',                   7,  true),
    ('REUNIAO',               'Reunião',                  8,  true),
    ('ANOTACAO_INTERNA',      'Anotação interna',         9,  true),
    ('OUTRO',                 'Outro',                    10, true),
    ('OMNI_AGENDAMENTO',      'Omni - Agendamento',      11, true)
ON CONFLICT DO NOTHING;


INSERT INTO tipos_unidade
    (codigo, nome, ordem, padrao_sistema)
VALUES
    ('MATRIZ',               'Matriz',                  1,  true),
    ('FILIAL',               'Filial',                  2,  true),
    ('ESCRITORIO',           'Escritório',              3,  true),
    ('LOJA',                 'Loja',                    4,  true),
    ('QUIOSQUE',             'Quiosque',                5,  true),
    ('FABRICA',              'Fábrica',                 6,  true),
    ('DISTRIBUIDORA',        'Distribuidora',           7,  true),
    ('CENTRO_DISTRIBUICAO',  'Centro de Distribuição',  8,  true),
    ('DEPOSITO',             'Depósito',                9,  true),
    ('POSTO_ATENDIMENTO',    'Posto de Atendimento',    10, true),
    ('HOME_OFFICE',          'Home Office',             11, true),
    ('OUTRO',                'Outro',                   12, true)
ON CONFLICT DO NOTHING;

COMMIT;