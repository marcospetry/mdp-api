BEGIN;

-- MDP 008 - Vínculo de usuários com tenants
--
-- Objetivo:
-- Criar o vínculo de acesso do usuário ao tenant sem alterar
-- o mecanismo atual baseado em usuarios_empresas.
--
-- Nesta etapa:
-- - usuarios_empresas continua intacta;
-- - sessoes_usuario continua usando empresa_id;
-- - login/MFA não são alterados;
-- - perfis existentes são reutilizados;
-- - nenhum código da API depende ainda desta tabela.

CREATE TABLE IF NOT EXISTS usuarios_tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    usuario_id UUID NOT NULL
        REFERENCES usuarios(id) ON DELETE CASCADE,

    tenant_id UUID NOT NULL
        REFERENCES tenants(id) ON DELETE CASCADE,

    perfil_id UUID NOT NULL
        REFERENCES perfis(id),

    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT usuarios_tenants_usuario_tenant_key
        UNIQUE (usuario_id, tenant_id)
);

CREATE INDEX IF NOT EXISTS ix_usuarios_tenants_usuario
    ON usuarios_tenants (usuario_id);

CREATE INDEX IF NOT EXISTS ix_usuarios_tenants_tenant
    ON usuarios_tenants (tenant_id);

CREATE INDEX IF NOT EXISTS ix_usuarios_tenants_tenant_ativo
    ON usuarios_tenants (tenant_id, ativo);

COMMENT ON TABLE usuarios_tenants IS
'Vincula usuários aos tenants da plataforma e define o perfil do usuário dentro de cada tenant.';

-- Backfill inicial.
--
-- Enquanto a aplicação ainda utiliza usuarios_empresas,
-- copiamos para o Tenant MDP os vínculos existentes da empresa MDP.
--
-- Não utilizamos UUID fixo do tenant: ele é localizado pelo código MDP.
-- Não utilizamos UUID fixo da empresa: ela é localizada pelo slug mdp.

INSERT INTO usuarios_tenants (
    usuario_id,
    tenant_id,
    perfil_id,
    ativo
)
SELECT
    ue.usuario_id,
    t.id,
    ue.perfil_id,
    ue.ativo
FROM usuarios_empresas ue
JOIN empresas e
    ON e.id = ue.empresa_id
JOIN tenants t
    ON t.codigo = 'MDP'
WHERE e.slug = 'mdp'
ON CONFLICT (usuario_id, tenant_id) DO NOTHING;

COMMIT;