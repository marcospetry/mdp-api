BEGIN;

ALTER TABLE sessoes_usuario
    ADD COLUMN IF NOT EXISTS contexto_tipo VARCHAR(20),
    ADD COLUMN IF NOT EXISTS tenant_id UUID,
    ADD COLUMN IF NOT EXISTS empresa_id UUID;

UPDATE sessoes_usuario
SET contexto_tipo = 'TENANT'
WHERE contexto_tipo IS NULL;

ALTER TABLE sessoes_usuario
    ALTER COLUMN contexto_tipo SET NOT NULL;

ALTER TABLE sessoes_usuario
    ADD CONSTRAINT sessoes_usuario_contexto_tipo_check
    CHECK (contexto_tipo IN ('PLATAFORMA','TENANT'));

CREATE INDEX IF NOT EXISTS idx_sessoes_usuario_tenant
    ON sessoes_usuario (tenant_id);

COMMIT;
