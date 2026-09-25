BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =========================================================
-- 1. USUÁRIOS / IDENTIDADE DA PLATAFORMA
-- =========================================================

CREATE TABLE usuarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash TEXT NOT NULL,

    is_superadmin BOOLEAN NOT NULL DEFAULT FALSE,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    ultimo_login_em TIMESTAMPTZ,

    mfa_habilitado BOOLEAN NOT NULL DEFAULT FALSE,
    mfa_secret_enc TEXT,
    mfa_confirmado_em TIMESTAMPTZ,

    senha_alterada_em TIMESTAMPTZ,
    tentativas_login INTEGER NOT NULL DEFAULT 0,
    bloqueado_ate TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_usuarios_email UNIQUE (email)
);

-- =========================================================
-- 2. TENANTS
-- =========================================================

CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo VARCHAR(50) NOT NULL,
    nome VARCHAR(150) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_tenants_codigo UNIQUE (codigo),
    CONSTRAINT uq_tenants_slug UNIQUE (slug)
);

-- =========================================================
-- 3. VÍNCULO USUÁRIO <-> TENANT
-- =========================================================

CREATE TABLE usuarios_tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_usuarios_tenants_usuario
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_usuarios_tenants_tenant
        FOREIGN KEY (tenant_id)
        REFERENCES tenants(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_usuarios_tenants
        UNIQUE (usuario_id, tenant_id)
);

-- =========================================================
-- 4. PAPÉIS ADMINISTRATIVOS DA PLATAFORMA
-- =========================================================

CREATE TABLE papeis_plataforma (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo VARCHAR(50) NOT NULL,
    nome VARCHAR(100) NOT NULL,
    descricao TEXT,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_papeis_plataforma_codigo UNIQUE (codigo)
);

CREATE TABLE usuarios_papeis_plataforma (
    usuario_id UUID NOT NULL,
    papel_id UUID NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (usuario_id, papel_id),

    CONSTRAINT fk_usuarios_papeis_usuario
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_usuarios_papeis_papel
        FOREIGN KEY (papel_id)
        REFERENCES papeis_plataforma(id)
        ON DELETE CASCADE
);

-- =========================================================
-- 5. FUNCIONALIDADES DISPONÍVEIS NA PLATAFORMA
-- =========================================================

CREATE TABLE funcionalidades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo VARCHAR(100) NOT NULL,
    nome VARCHAR(150) NOT NULL,
    descricao TEXT,

    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    ordem INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_funcionalidades_codigo UNIQUE (codigo)
);

-- =========================================================
-- 6. FUNCIONALIDADES HABILITADAS POR TENANT
-- =========================================================

CREATE TABLE tenants_funcionalidades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    tenant_id UUID NOT NULL,
    funcionalidade_id UUID NOT NULL,

    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    habilitado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    desabilitado_em TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_tenants_funcionalidades_tenant
        FOREIGN KEY (tenant_id)
        REFERENCES tenants(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_tenants_funcionalidades_funcionalidade
        FOREIGN KEY (funcionalidade_id)
        REFERENCES funcionalidades(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_tenants_funcionalidades
        UNIQUE (tenant_id, funcionalidade_id)
);

-- =========================================================
-- 7. REGISTRO DOS BANCOS DOS TENANTS
-- =========================================================

CREATE TABLE tenant_databases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    tenant_id UUID NOT NULL,

    tipo_infra VARCHAR(30) NOT NULL DEFAULT 'MDP_SHARED',

    host VARCHAR(255) NOT NULL,
    porta INTEGER NOT NULL DEFAULT 5432,
    database_name VARCHAR(150) NOT NULL,
    username VARCHAR(150) NOT NULL,

    -- Nunca armazenar senha diretamente aqui.
    secret_ref TEXT,

    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    versao_schema VARCHAR(50),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_tenant_databases_tenant
        FOREIGN KEY (tenant_id)
        REFERENCES tenants(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_tenant_databases_tenant
        UNIQUE (tenant_id),

    CONSTRAINT uq_tenant_databases_database_name
        UNIQUE (database_name)
);

-- =========================================================
-- 8. CONTROLE DE PROVISIONAMENTO
-- =========================================================

CREATE TABLE provisionamentos_tenant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    tenant_id UUID NOT NULL,

    status VARCHAR(30) NOT NULL,
    iniciado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    concluido_em TIMESTAMPTZ,

    detalhe TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_provisionamentos_tenant
        FOREIGN KEY (tenant_id)
        REFERENCES tenants(id)
        ON DELETE CASCADE
);

-- =========================================================
-- 9. VERSIONAMENTO DO SCHEMA DOS TENANTS
-- =========================================================

CREATE TABLE versoes_tenant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    tenant_id UUID NOT NULL,

    versao VARCHAR(50) NOT NULL,
    aplicada_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    descricao TEXT,

    CONSTRAINT fk_versoes_tenant
        FOREIGN KEY (tenant_id)
        REFERENCES tenants(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_versoes_tenant
        UNIQUE (tenant_id, versao)
);

-- =========================================================
-- 10. SESSÕES DA PLATAFORMA
-- Não existe mais empresa_id aqui.
-- =========================================================

CREATE TABLE sessoes_usuario (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    usuario_id UUID NOT NULL,

    refresh_token_hash TEXT NOT NULL,

    criada_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expira_em TIMESTAMPTZ NOT NULL,
    ultimo_uso_em TIMESTAMPTZ,
    revogada_em TIMESTAMPTZ,
    motivo_revogacao TEXT,

    ip_origem VARCHAR(100),
    user_agent TEXT,

    CONSTRAINT fk_sessoes_usuario
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE CASCADE
);

-- =========================================================
-- ÍNDICES
-- =========================================================

CREATE INDEX idx_usuarios_email
    ON usuarios(email);

CREATE INDEX idx_usuarios_tenants_usuario
    ON usuarios_tenants(usuario_id);

CREATE INDEX idx_usuarios_tenants_tenant
    ON usuarios_tenants(tenant_id);

CREATE INDEX idx_tenants_funcionalidades_tenant
    ON tenants_funcionalidades(tenant_id);

CREATE INDEX idx_tenant_databases_tenant
    ON tenant_databases(tenant_id);

CREATE INDEX idx_sessoes_usuario_usuario
    ON sessoes_usuario(usuario_id);

CREATE INDEX idx_sessoes_usuario_refresh_token_hash
    ON sessoes_usuario(refresh_token_hash);

COMMIT;