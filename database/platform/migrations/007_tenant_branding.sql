-- 007_tenant_branding.sql
-- Dominio e identidade visual do backoffice por Tenant. Aplicar SOMENTE em mdp_platform.
BEGIN;

CREATE TABLE IF NOT EXISTS tenant_branding (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
    admin_host VARCHAR(255),
    nome_exibicao VARCHAR(150),
    logo_url TEXT,
    favicon_url TEXT,
    cor_primaria VARCHAR(7),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_tenant_branding_cor_primaria CHECK (cor_primaria IS NULL OR cor_primaria ~ '^#[0-9A-Fa-f]{6}$'),
    CONSTRAINT ck_tenant_branding_admin_host CHECK (admin_host IS NULL OR admin_host ~ '^[A-Za-z0-9.-]+$')
);
ALTER TABLE tenant_branding OWNER TO mdp;
CREATE UNIQUE INDEX IF NOT EXISTS ux_tenant_branding_admin_host_lower
    ON tenant_branding (LOWER(admin_host)) WHERE admin_host IS NOT NULL;

COMMIT;
