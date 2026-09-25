BEGIN;

-- MDP 007 - Fundação de Tenants
--
-- Objetivo:
-- Criar a entidade Tenant como fronteira lógica de isolamento da plataforma.
--
-- IMPORTANTE:
-- Nesta etapa NÃO alteramos empresas, autenticação, sessões, perfis,
-- permissões ou qualquer módulo existente.
--
-- A tabela empresas continua funcionando exatamente como antes.
-- A associação entre usuários/dados e tenants será feita em migrations
-- posteriores, de forma incremental.

CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo VARCHAR(50) NOT NULL,
    nome VARCHAR(150) NOT NULL,
    slug VARCHAR(80) NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT tenants_codigo_key UNIQUE (codigo),
    CONSTRAINT tenants_slug_key UNIQUE (slug)
);

COMMENT ON TABLE tenants IS
'Fronteira lógica de isolamento multi-tenant da plataforma MDP. Tenant não é sinônimo de empresa/organização.';

COMMENT ON COLUMN tenants.codigo IS
'Código estável interno do tenant.';

COMMENT ON COLUMN tenants.slug IS
'Identificador textual do tenant para uso em contexto, configuração e URLs quando aplicável.';

-- Tenant inicial da plataforma:
-- a própria MDP Consultoria operando como cliente/tenant da plataforma.

INSERT INTO tenants (
    codigo,
    nome,
    slug,
    ativo
)
VALUES (
    'MDP',
    'MDP Consultoria',
    'mdp',
    TRUE
)
ON CONFLICT (codigo) DO NOTHING;

COMMIT;