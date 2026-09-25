-- 004_seed_tenant_endpoints_mdp.sql
-- Endpoints iniciais do Tenant MDP.
-- Pode ser executado novamente sem duplicar registros.

-- SITE
INSERT INTO tenant_endpoints (
    tenant_id, tipo, codigo, nome,
    identificador_publico, identificador_externo, url
)
SELECT id, 'SITE', 'SITE_MDP', 'Site MDP Consultoria',
       'mdpconsultoria.com.br', NULL, 'https://mdpconsultoria.com.br'
FROM tenants
WHERE codigo = 'MDP'
ON CONFLICT (tenant_id, codigo)
DO UPDATE SET
    tipo = EXCLUDED.tipo,
    nome = EXCLUDED.nome,
    identificador_publico = EXCLUDED.identificador_publico,
    identificador_externo = EXCLUDED.identificador_externo,
    url = EXCLUDED.url,
    ativo = TRUE,
    updated_at = NOW();

-- FORMULARIO
INSERT INTO tenant_endpoints (
    tenant_id, tipo, codigo, nome,
    identificador_publico, identificador_externo, url, configuracao
)
SELECT id, 'FORMULARIO', 'FORM_CONTATO_MDP', 'Formulario de Contato MDP',
       'FORM_CONTATO_MDP', NULL, 'https://mdpconsultoria.com.br/#contato',
       '{"empresa_slug": "mdp"}'::jsonb
FROM tenants
WHERE codigo = 'MDP'
ON CONFLICT (tenant_id, codigo)
DO UPDATE SET
    tipo = EXCLUDED.tipo,
    nome = EXCLUDED.nome,
    identificador_publico = EXCLUDED.identificador_publico,
    identificador_externo = EXCLUDED.identificador_externo,
    url = EXCLUDED.url,
    configuracao = EXCLUDED.configuracao,
    ativo = TRUE,
    updated_at = NOW();

-- WHATSAPP
INSERT INTO tenant_endpoints (
    tenant_id, tipo, codigo, nome,
    identificador_publico, identificador_externo, url
)
SELECT id, 'WHATSAPP', 'WHATSAPP_MDP', 'WhatsApp MDP Consultoria',
       '4198059899', NULL, NULL
FROM tenants
WHERE codigo = 'MDP'
ON CONFLICT (tenant_id, codigo)
DO UPDATE SET
    tipo = EXCLUDED.tipo,
    nome = EXCLUDED.nome,
    identificador_publico = EXCLUDED.identificador_publico,
    identificador_externo = EXCLUDED.identificador_externo,
    url = EXCLUDED.url,
    ativo = TRUE,
    updated_at = NOW();

-- INSTAGRAM
INSERT INTO tenant_endpoints (
    tenant_id, tipo, codigo, nome,
    identificador_publico, identificador_externo, url
)
SELECT id, 'INSTAGRAM', 'INSTAGRAM_MDP', 'Instagram MDP Consultoria',
       'mdp.ia', NULL, 'https://www.instagram.com/mdp.ia/'
FROM tenants
WHERE codigo = 'MDP'
ON CONFLICT (tenant_id, codigo)
DO UPDATE SET
    tipo = EXCLUDED.tipo,
    nome = EXCLUDED.nome,
    identificador_publico = EXCLUDED.identificador_publico,
    identificador_externo = EXCLUDED.identificador_externo,
    url = EXCLUDED.url,
    ativo = TRUE,
    updated_at = NOW();
