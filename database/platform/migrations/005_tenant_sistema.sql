BEGIN;

ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS tenant_sistema boolean NOT NULL DEFAULT false;

UPDATE tenants
SET tenant_sistema = true
WHERE id = 'c2f4e821-4894-4d67-ba38-0aedaaec3a39'::uuid
  AND codigo = 'MDP';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM tenants
        WHERE id = 'c2f4e821-4894-4d67-ba38-0aedaaec3a39'::uuid
          AND codigo = 'MDP'
          AND tenant_sistema = true
    ) THEN
        RAISE EXCEPTION 'Tenant MDP oficial nao encontrado; migration interrompida.';
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS ux_tenants_unico_sistema
    ON tenants (tenant_sistema)
    WHERE tenant_sistema = true;

COMMIT;
