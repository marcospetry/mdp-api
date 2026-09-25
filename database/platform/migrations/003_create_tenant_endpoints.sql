-- 003_create_tenant_endpoints.sql
-- Pontos externos de identificação e roteamento dos tenants.
-- Esta tabela pertence ao mdp_platform.
--
-- Exemplos futuros:
-- SITE        -> mdpconsultoria.com.br
-- FORMULARIO  -> FORM_CONTATO_MDP
-- WHATSAPP    -> phone_number_id da Meta
-- INSTAGRAM   -> identificador da conta/pagina Meta
-- OMNI_LINK   -> slug/link público do tenant

CREATE TABLE tenant_endpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    tenant_id UUID NOT NULL,

    tipo VARCHAR(50) NOT NULL,
    codigo VARCHAR(100) NOT NULL,
    nome VARCHAR(150) NOT NULL,

identificador_publico VARCHAR(255),
identificador_externo VARCHAR(255),
url TEXT,

    configuracao JSONB NOT NULL DEFAULT '{}'::jsonb,

    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_tenant_endpoints_tenant
        FOREIGN KEY (tenant_id)
        REFERENCES tenants(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_tenant_endpoints_codigo
        UNIQUE (tenant_id, codigo)
);

ALTER TABLE tenant_endpoints OWNER TO mdp;

CREATE INDEX idx_tenant_endpoints_tenant
    ON tenant_endpoints(tenant_id);

CREATE INDEX idx_tenant_endpoints_tipo_identificador
    ON tenant_endpoints(tipo, identificador_externo)
    WHERE ativo = TRUE;