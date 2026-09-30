-- 006_provedores_aplicacoes.sql
-- Cadastro global de provedores e aplicacoes externas da Plataforma MDP.
-- Aplicar SOMENTE em mdp_platform. Segredos nao sao armazenados aqui, apenas referencias seguras.
BEGIN;

CREATE TABLE IF NOT EXISTS provedores_integracao (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nome VARCHAR(150) NOT NULL,
    descricao TEXT,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE provedores_integracao OWNER TO mdp;

CREATE TABLE IF NOT EXISTS aplicacoes_integracao (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provedor_id UUID NOT NULL REFERENCES provedores_integracao(id) ON DELETE RESTRICT,
    codigo VARCHAR(100) NOT NULL UNIQUE,
    nome VARCHAR(150) NOT NULL,
    app_id VARCHAR(255),
    owner_business_id VARCHAR(255),
    embedded_signup_config_id VARCHAR(255),
    graph_api_version VARCHAR(50),
    modo VARCHAR(30),
    status_revisao VARCHAR(50),
    callback_url TEXT,
    permissoes JSONB NOT NULL DEFAULT '[]'::jsonb,
    webhook_campos JSONB NOT NULL DEFAULT '[]'::jsonb,
    app_secret_ref TEXT,
    access_token_ref TEXT,
    verify_token_ref TEXT,
    observacoes TEXT,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE aplicacoes_integracao OWNER TO mdp;
CREATE INDEX IF NOT EXISTS idx_aplicacoes_integracao_provedor ON aplicacoes_integracao(provedor_id);

INSERT INTO provedores_integracao(codigo,nome,descricao,ativo)
VALUES ('META','Meta','Meta Platforms - provedor global para WhatsApp, Instagram e Facebook.',true)
ON CONFLICT (codigo) DO UPDATE SET nome=EXCLUDED.nome, descricao=EXCLUDED.descricao;

COMMIT;
