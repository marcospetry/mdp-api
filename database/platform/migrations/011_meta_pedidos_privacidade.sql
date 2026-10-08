-- 011_meta_pedidos_privacidade.sql
-- Aplicar SOMENTE em mdp_platform. Validar primeiro em DEV. Idempotente.
--
-- Registro dos pedidos que a Meta envia quando o dono de uma conta remove o app (desautorizacao)
-- ou pede a exclusao dos seus dados. Guarda SO o necessario para provar o atendimento e para a
-- pagina publica de status: codigo, ID da Meta, tipo, situacao e datas. Nunca guarda conteudo de mensagens.
BEGIN;

CREATE TABLE IF NOT EXISTS meta_pedidos_privacidade (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo          VARCHAR(32)  NOT NULL,
    tipo            VARCHAR(20)  NOT NULL,
    meta_user_id    VARCHAR(255) NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'RECEBIDO',
    canais_afetados INTEGER      NOT NULL DEFAULT 0,
    tenant_id       UUID REFERENCES tenants(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    concluido_em    TIMESTAMPTZ,
    CONSTRAINT uq_meta_pedidos_privacidade_codigo UNIQUE (codigo),
    CONSTRAINT ck_meta_pedidos_privacidade_tipo   CHECK (tipo IN ('DESAUTORIZACAO', 'EXCLUSAO')),
    CONSTRAINT ck_meta_pedidos_privacidade_status CHECK (status IN ('RECEBIDO', 'CONCLUIDO', 'SEM_CORRESPONDENCIA'))
);

ALTER TABLE meta_pedidos_privacidade OWNER TO mdp;

CREATE INDEX IF NOT EXISTS idx_meta_pedidos_privacidade_user
    ON meta_pedidos_privacidade (meta_user_id, created_at DESC);

COMMENT ON TABLE meta_pedidos_privacidade IS
    'Pedidos de desautorizacao e de exclusao de dados recebidos da Meta. Sem conteudo de mensagens; o codigo e o que a pagina publica de status consulta.';
COMMENT ON COLUMN meta_pedidos_privacidade.meta_user_id IS
    'user_id do signed_request (ID do usuario NO APP, nao necessariamente o ID da conta que roteia webhooks).';

COMMIT;
