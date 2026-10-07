-- 010_omni_conexoes_roteamento.sql
-- Aplicar SOMENTE em mdp_platform. Validar primeiro em DEV (postgres-mdp, localhost:5432).
-- Idempotente: pode ser executada mais de uma vez.
--
-- O que faz:
--   1. Garante unicidade do roteamento de canais (webhook -> tenant).
--   2. usuarios: dispensa de MFA CONTROLADA (somente nao-SUPERADMIN, com validade)
--      e validade de acesso (usada pelo usuario de revisao da Meta).
--   3. canal_conexoes: conexao tecnica de cada canal (token criptografado, escopos,
--      validade, status do webhook), separada do cadastro do canal (tenant_endpoints).
BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Roteamento unico: um identificador externo ativo pertence a UM tenant
-- ---------------------------------------------------------------------------
DO $$
DECLARE dup text;
BEGIN
    SELECT string_agg(format('tipo_endpoint_id=%s identificador_externo=%s (%s registros)',
                             tipo_endpoint_id, identificador_externo, n), E'\n')
      INTO dup
      FROM (SELECT tipo_endpoint_id, identificador_externo, count(*) AS n
              FROM tenant_endpoints
             WHERE ativo = TRUE AND identificador_externo IS NOT NULL
             GROUP BY tipo_endpoint_id, identificador_externo
            HAVING count(*) > 1) d;
    IF dup IS NOT NULL THEN
        RAISE EXCEPTION E'Migration 010 interrompida: identificadores externos ativos duplicados em tenant_endpoints.\nResolva (inative ou corrija) antes de repetir:\n%', dup;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_tenant_endpoints_tipo_externo_ativo
    ON tenant_endpoints (tipo_endpoint_id, identificador_externo)
    WHERE ativo = TRUE AND identificador_externo IS NOT NULL;

-- O indice unico passa a atender a mesma consulta; remove o nao unico redundante.
DROP INDEX IF EXISTS idx_tenant_endpoints_tipo_identificador;

-- ---------------------------------------------------------------------------
-- 2. usuarios: MFA dispensado com validade + validade de acesso
-- ---------------------------------------------------------------------------
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS mfa_dispensado   BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS acesso_expira_em TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_usuarios_mfa_dispensado') THEN
        ALTER TABLE usuarios ADD CONSTRAINT ck_usuarios_mfa_dispensado
            CHECK (NOT mfa_dispensado
                   OR (is_superadmin = FALSE AND mfa_habilitado = FALSE AND acesso_expira_em IS NOT NULL));
    END IF;
END $$;

COMMENT ON COLUMN usuarios.mfa_dispensado IS
    'Excecao controlada de MFA (ex.: usuario de App Review da Meta). Nunca para SUPERADMIN; exige acesso_expira_em; so pode ser ligada por SUPERADMIN.';
COMMENT ON COLUMN usuarios.acesso_expira_em IS
    'Quando preenchida, o login e o refresh sao recusados apos esta data. Obrigatoria se mfa_dispensado = TRUE.';

-- ---------------------------------------------------------------------------
-- 3. canal_conexoes: conexao tecnica de um canal (1 por endpoint)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS canal_conexoes (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    endpoint_id              UUID NOT NULL REFERENCES tenant_endpoints(id) ON DELETE CASCADE,
    aplicacao_id             UUID REFERENCES aplicacoes_integracao(id) ON DELETE RESTRICT,

    tipo_conexao             VARCHAR(30) NOT NULL,
    status                   VARCHAR(20) NOT NULL DEFAULT 'PENDENTE',

    escopos                  JSONB NOT NULL DEFAULT '[]'::jsonb,

    token_tipo               VARCHAR(30),
    token_enc                TEXT,
    token_key_version        SMALLINT NOT NULL DEFAULT 1,
    token_expira_em          TIMESTAMPTZ,
    renovar_em               TIMESTAMPTZ,

    webhook_assinado         BOOLEAN NOT NULL DEFAULT FALSE,
    webhook_campos           JSONB NOT NULL DEFAULT '[]'::jsonb,
    webhook_verificado_em    TIMESTAMPTZ,

    metadados                JSONB NOT NULL DEFAULT '{}'::jsonb,

    conectado_por_usuario_id UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    conectado_em             TIMESTAMPTZ,
    desconectado_em          TIMESTAMPTZ,
    ultimo_erro              TEXT,
    ultimo_erro_em           TIMESTAMPTZ,

    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_canal_conexoes_endpoint UNIQUE (endpoint_id),
    CONSTRAINT ck_canal_conexoes_tipo
        CHECK (tipo_conexao IN ('INSTAGRAM_LOGIN', 'FACEBOOK_PAGE', 'WHATSAPP')),
    CONSTRAINT ck_canal_conexoes_status
        CHECK (status IN ('PENDENTE', 'CONECTADO', 'EXPIRANDO', 'EXPIRADO', 'REVOGADO', 'ERRO')),
    CONSTRAINT ck_canal_conexoes_token_tipo
        CHECK (token_tipo IS NULL OR token_tipo IN ('IG_LONG_LIVED', 'PAGE_TOKEN', 'SYSTEM_USER', 'BUSINESS_TOKEN')),
    CONSTRAINT ck_canal_conexoes_conectado_com_token
        CHECK (status <> 'CONECTADO' OR token_enc IS NOT NULL)
);

ALTER TABLE canal_conexoes OWNER TO mdp;

CREATE INDEX IF NOT EXISTS idx_canal_conexoes_tenant ON canal_conexoes (tenant_id);
CREATE INDEX IF NOT EXISTS idx_canal_conexoes_renovacao
    ON canal_conexoes (renovar_em) WHERE status IN ('CONECTADO', 'EXPIRANDO');

COMMENT ON TABLE  canal_conexoes IS
    'Conexao tecnica (OAuth) de um canal cadastrado em tenant_endpoints. IDs que roteiam webhook ficam em tenant_endpoints.identificador_externo.';
COMMENT ON COLUMN canal_conexoes.token_enc IS
    'Token criptografado (Fernet) com chave propria (nao a do MFA). Nunca retornar pela API nem registrar em log. token_key_version permite rotacionar a chave.';
COMMENT ON COLUMN canal_conexoes.metadados IS
    'Dados nao sensiveis da conta conectada (nome, @usuario, foto, IDs alternativos). Ex.: Instagram expoe mais de um ID (o do webhook entry.id e o do /me); conferir durante o OAuth qual deles roteia o webhook.';

COMMIT;
