BEGIN;

-- MDP 009 - Associação de empresas a tenants
--
-- Objetivo:
-- Introduzir explicitamente a propriedade de uma empresa/organização
-- por um tenant, sem alterar o mecanismo atual de autenticação.
--
-- Compatibilidade:
-- - empresas continua existindo;
-- - usuarios_empresas continua usando empresa_id;
-- - sessoes_usuario continua usando empresa_id;
-- - login/MFA não são alterados;
-- - tenant_id permanece nullable nesta fase.

ALTER TABLE empresas
    ADD COLUMN IF NOT EXISTS tenant_id UUID;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'empresas_tenant_id_fkey'
    ) THEN
        ALTER TABLE empresas
            ADD CONSTRAINT empresas_tenant_id_fkey
            FOREIGN KEY (tenant_id)
            REFERENCES tenants(id)
            ON DELETE RESTRICT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_empresas_tenant
    ON empresas (tenant_id);

COMMENT ON COLUMN empresas.tenant_id IS
'Tenant proprietário da empresa/organização. Nullable durante a transição do modelo legado.';

-- Associa a empresa operacional MDP ao Tenant MDP.
-- Não usa UUID fixo para funcionar também em outros ambientes.

UPDATE empresas e
SET tenant_id = t.id
FROM tenants t
WHERE e.slug = 'mdp'
  AND t.codigo = 'MDP'
  AND e.tenant_id IS NULL;

COMMIT;