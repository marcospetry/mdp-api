BEGIN;

-- As sessoes anteriores ao novo modelo de contexto podem ser descartadas.
DELETE FROM sessoes_usuario;

ALTER TABLE sessoes_usuario
    ADD COLUMN IF NOT EXISTS contexto_tipo VARCHAR(20),
    ADD COLUMN IF NOT EXISTS tenant_id UUID,
    ADD COLUMN IF NOT EXISTS empresa_id UUID;

ALTER TABLE sessoes_usuario
    ALTER COLUMN contexto_tipo SET NOT NULL;

ALTER TABLE sessoes_usuario
    ADD CONSTRAINT sessoes_usuario_contexto_tipo_check
    CHECK (contexto_tipo IN ('PLATAFORMA','TENANT'));

CREATE INDEX IF NOT EXISTS idx_sessoes_usuario_tenant
    ON sessoes_usuario (tenant_id);

COMMIT;